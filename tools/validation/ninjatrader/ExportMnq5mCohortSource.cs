#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

// Install this file as a NinjaTrader 8 indicator. It captures source/provenance
// only. It contains no hierarchy, oracle, comparison, or trading logic.
namespace NinjaTrader.NinjaScript.Indicators
{
    public class ExportMnq5mCohortSource : Indicator
    {
        private const string ApprovedFullName = "MNQ 09-26";
        private const int ApprovedExpiryMonth = 9;
        private const int ApprovedExpiryYear = 2026;
        private const int RequiredBars = 250;
        private static readonly Encoding Utf8NoBom = new UTF8Encoding(false);

        private bool exported;
        private bool armed;
        private DateTimeOffset initializedAtPc;
        private DateTimeOffset armedAtPc;
        private SessionIterator sessionIterator;

        [NinjaScriptProperty]
        [Display(Name = "Acquisition ID", Order = 1)]
        public string AcquisitionId { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Cohort ID", Order = 2)]
        public string CohortId { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Case ID", Order = 3)]
        public string CaseId { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trading date (yyyy-MM-dd)", Order = 4)]
        public string TradingDateText { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Operator arm file", Order = 5)]
        public string ArmFilePath { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Exports a controlled MNQ SEP26 native 5-minute source and runtime metadata.";
                Name = "ExportMnq5mCohortSource";
                Calculate = Calculate.OnBarClose;
                IsOverlay = false;
                AcquisitionId = string.Empty;
                CohortId = "mnq-202609-5m-v1";
                CaseId = string.Empty;
                TradingDateText = string.Empty;
                ArmFilePath = string.Empty;
            }
            else if (State == State.DataLoaded)
            {
                ValidateRuntimeSeries();
                sessionIterator = new SessionIterator(Bars);
                initializedAtPc = DateTimeOffset.Now;
                Log(
                    "acquisition=" + AcquisitionId + " exporter initialized event_time="
                    + initializedAtPc.ToString("o", CultureInfo.InvariantCulture),
                    LogLevel.Information);
            }
            else if (State == State.Realtime)
                Log(
                    "acquisition=" + AcquisitionId
                    + " awaiting operator arm after Reload All Historical Data",
                    LogLevel.Information);
        }

        protected override void OnBarUpdate()
        {
            // Historical calculation is deliberately inert. The operator must invoke
            // Reload All Historical Data, wait for the chart to return to Realtime,
            // and only then create/update the acquisition-specific arm file.
            if (exported || State != State.Realtime || CurrentBar < Count - 2)
                return;
            if (!TryArmAcquisition())
                return;

            DateTime tradingDate;
            if (!DateTime.TryParseExact(
                    TradingDateText,
                    "yyyy-MM-dd",
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.None,
                    out tradingDate))
                throw new InvalidOperationException("TradingDateText must use yyyy-MM-dd.");

            DateTime approvedStart = new DateTime(2026, 6, 22);
            DateTime approvedEnd = new DateTime(2026, 7, 24);
            if (tradingDate.Date < approvedStart || tradingDate.Date > approvedEnd)
                throw new InvalidOperationException("Trading date is outside the approved cohort range.");

            List<int> matchingBarsAgo = new List<int>();
            for (int barsAgo = Count - 2; barsAgo >= 0; barsAgo--)
            {
                DateTime barTradingDay = sessionIterator.GetTradingDay(Time[barsAgo]).Date;
                if (barTradingDay == tradingDate.Date)
                    matchingBarsAgo.Add(barsAgo);
            }

            if (matchingBarsAgo.Count < RequiredBars)
                throw new InvalidOperationException(
                    "The selected trading session contains fewer than 250 closed native bars.");

            // The protocol predeclares the first 250 native bars of the session.
            // This is explicit selection, never silent truncation or repair.
            List<int> selected = matchingBarsAgo.Take(RequiredBars).ToList();
            IList<object> connectionsAtArm = CaptureActiveConnections();
            ExportBundle(tradingDate.Date, selected, connectionsAtArm);
            exported = true;
        }

        private bool TryArmAcquisition()
        {
            if (armed)
                return true;
            if (!File.Exists(ArmFilePath))
                return false;
            if (File.GetLastWriteTimeUtc(ArmFilePath) <= initializedAtPc.UtcDateTime)
                return false;
            if (File.ReadAllText(ArmFilePath).Trim() != AcquisitionId)
                throw new InvalidOperationException(
                    "Operator arm file must contain the exact AcquisitionId.");

            armedAtPc = DateTimeOffset.Now;
            armed = true;
            Log(
                "acquisition=" + AcquisitionId
                + " export armed after reload event_time="
                + armedAtPc.ToString("o", CultureInfo.InvariantCulture),
                LogLevel.Information);
            return true;
        }

        private void ValidateRuntimeSeries()
        {
            if (string.IsNullOrWhiteSpace(AcquisitionId)
                || string.IsNullOrWhiteSpace(CohortId)
                || string.IsNullOrWhiteSpace(CaseId)
                || string.IsNullOrWhiteSpace(ArmFilePath)
                || !Path.IsPathRooted(ArmFilePath))
                throw new InvalidOperationException(
                    "AcquisitionId, CohortId, CaseId, and an absolute ArmFilePath are required.");

            DateTime expiry = ReadDateTimeProperty(Instrument, "Expiry");
            string masterName = Instrument.MasterInstrument.Name;
            if (Instrument.FullName != ApprovedFullName
                || masterName != "MNQ"
                || expiry.Month != ApprovedExpiryMonth
                || expiry.Year != ApprovedExpiryYear)
                throw new InvalidOperationException(
                    "Runtime instrument is not the approved MNQ SEP26 / MNQ 09-26 contract.");

            if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute
                || BarsPeriod.Value != 5)
                throw new InvalidOperationException(
                    "Runtime series must be native 5-minute Minute bars.");
        }

        private void ExportBundle(
            DateTime tradingDate,
            IList<int> selected,
            IList<object> connectionsAtArm)
        {
            TimeZoneInfo applicationTimeZone = Core.Globals.GeneralOptions.TimeZoneInfo;
            TimeZoneInfo pcTimeZone = TimeZoneInfo.Local;
            TradingHours appliedTradingHours = Bars.TradingHours;
            if (applicationTimeZone == null)
                throw new InvalidOperationException("NinjaTrader application timezone is unavailable.");
            if (appliedTradingHours == null
                || string.IsNullOrWhiteSpace(appliedTradingHours.Name)
                || appliedTradingHours.TimeZoneInfo == null)
                throw new InvalidOperationException("Applied Trading Hours metadata is unavailable.");

            string root = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                "MNQ_5m_Acquisitions",
                MakeSafeFileName(AcquisitionId));
            if (Directory.Exists(root))
                throw new InvalidOperationException(
                    "The acquisition output directory already exists; refusing to overwrite it.");
            Directory.CreateDirectory(root);

            string sourcePath = Path.Combine(root, "bars.txt");
            string runtimePath = Path.Combine(root, "runtime_capture.json");
            string sourceTemporary = sourcePath + ".tmp";
            string runtimeTemporary = runtimePath + ".tmp";
            string tradingHoursCopy = Path.Combine(root, "trading_hours_template.xml");
            string configCopy = Path.Combine(root, "NinjaTrader.Config.xml");

            List<string> rows = new List<string>();
            foreach (int barsAgo in selected)
            {
                rows.Add(string.Join(
                    ";",
                    Time[barsAgo].ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture),
                    Open[barsAgo].ToString("R", CultureInfo.InvariantCulture),
                    High[barsAgo].ToString("R", CultureInfo.InvariantCulture),
                    Low[barsAgo].ToString("R", CultureInfo.InvariantCulture),
                    Close[barsAgo].ToString("R", CultureInfo.InvariantCulture),
                    Volume[barsAgo].ToString(CultureInfo.InvariantCulture)));
            }
            File.WriteAllText(sourceTemporary, string.Join(Environment.NewLine, rows) + Environment.NewLine, Utf8NoBom);
            File.Move(sourceTemporary, sourcePath);

            string userData = Core.Globals.UserDataDir;
            string tradingHoursPath = Path.Combine(
                userData,
                "templates",
                "TradingHours",
                appliedTradingHours.Name + ".xml");
            string configPath = Path.Combine(userData, "Config.xml");
            if (!File.Exists(tradingHoursPath) || !File.Exists(configPath))
                throw new InvalidOperationException(
                    "Trading Hours template or NinjaTrader configuration file is unavailable.");
            File.Copy(tradingHoursPath, tradingHoursCopy, false);
            File.Copy(configPath, configCopy, false);

            DateTimeOffset exportedUtc = DateTimeOffset.UtcNow;
            DateTimeOffset exportedAt = TimeZoneInfo.ConvertTime(
                exportedUtc,
                applicationTimeZone);
            DateTimeOffset exportedAtPc = TimeZoneInfo.ConvertTime(exportedUtc, pcTimeZone);

            object runtimeCapture = new
            {
                schema_version = "1.0",
                acquisition_id = AcquisitionId,
                cohort_id = CohortId,
                case_id = CaseId,
                trading_date = tradingDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
                instrument = new
                {
                    contract_label = "MNQ SEP26",
                    full_name = Instrument.FullName,
                    master_name = Instrument.MasterInstrument.Name,
                    instrument_id = Instrument.FullName,
                    expiry_month = ReadDateTimeProperty(Instrument, "Expiry").Month,
                    expiry_year = ReadDateTimeProperty(Instrument, "Expiry").Year,
                    exchange = Instrument.Exchange.ToString()
                },
                ninjatrader_version = typeof(Instrument).Assembly.GetName().Version.ToString(),
                export_method = "ExportMnq5mCohortSource NinjaTrader indicator",
                original_export_identity = AcquisitionId + "/bars.txt",
                bar_series = new
                {
                    type = BarsPeriod.BarsPeriodType.ToString(),
                    value = BarsPeriod.Value,
                    native = true,
                    exported_bar_count = selected.Count,
                    timestamp_semantics = "NinjaTrader native Minute bar close timestamp from Time[0], displayed in the application timezone"
                },
                pc_timezone = new
                {
                    id = pcTimeZone.Id,
                    base_utc_offset = FormatOffset(pcTimeZone.BaseUtcOffset),
                    supports_dst = pcTimeZone.SupportsDaylightSavingTime,
                    acquisition_event_offsets = new[]
                    {
                        CaptureEventOffset("initialized", initializedAtPc),
                        CaptureEventOffset("armed", armedAtPc),
                        CaptureEventOffset("exported", exportedAtPc)
                    }
                },
                application_timezone = new
                {
                    id = applicationTimeZone.Id,
                    display_name = applicationTimeZone.DisplayName,
                    standard_name = applicationTimeZone.StandardName,
                    daylight_name = applicationTimeZone.DaylightName,
                    base_utc_offset = FormatOffset(applicationTimeZone.BaseUtcOffset),
                    supports_dst = applicationTimeZone.SupportsDaylightSavingTime,
                    source_timestamp_offsets = CaptureSourceOffsetRuns(
                        selected,
                        applicationTimeZone)
                },
                trading_hours = new
                {
                    name = appliedTradingHours.Name,
                    timezone_id = appliedTradingHours.TimeZoneInfo.Id,
                    definition_sha256 = Sha256(tradingHoursCopy),
                    holiday_configuration_captured = true,
                    session_calendar = CaptureSessionCalendar(tradingDate, applicationTimeZone)
                },
                active_connections = connectionsAtArm,
                connection_snapshot_phase = "immediately after operator arm and before export",
                exported_at = exportedAt.ToString("o", CultureInfo.InvariantCulture),
                source_sha256 = Sha256(sourcePath)
            };

            File.WriteAllText(
                runtimeTemporary,
                JsonConvert.SerializeObject(runtimeCapture, Formatting.Indented) + Environment.NewLine,
                Utf8NoBom);
            File.Move(runtimeTemporary, runtimePath);

            Log(
                "acquisition=" + AcquisitionId
                + " export complete event_time="
                + exportedAtPc.ToString("o", CultureInfo.InvariantCulture)
                + " source_sha256=" + Sha256(sourcePath),
                LogLevel.Information);
            Print(
                "acquisition=" + AcquisitionId
                + " export complete source_sha256=" + Sha256(sourcePath)
                + " runtime_capture=" + runtimePath);
        }

        private object CaptureEventOffset(string eventName, DateTimeOffset timestamp)
        {
            return new
            {
                @event = eventName,
                timestamp = timestamp.ToString("o", CultureInfo.InvariantCulture),
                utc_offset = FormatOffset(timestamp.Offset)
            };
        }

        private IList<object> CaptureSourceOffsetRuns(
            IList<int> selected,
            TimeZoneInfo applicationTimeZone)
        {
            List<object> runs = new List<object>();
            int runStart = 0;
            TimeSpan runOffset = applicationTimeZone.GetUtcOffset(Time[selected[0]]);
            for (int index = 1; index < selected.Count; index++)
            {
                TimeSpan offset = applicationTimeZone.GetUtcOffset(Time[selected[index]]);
                if (offset == runOffset)
                    continue;
                runs.Add(CaptureSourceOffsetRun(
                    selected[runStart],
                    selected[index - 1],
                    runOffset));
                runStart = index;
                runOffset = offset;
            }
            runs.Add(CaptureSourceOffsetRun(
                selected[runStart],
                selected[selected.Count - 1],
                runOffset));
            return runs;
        }

        private object CaptureSourceOffsetRun(
            int firstBarsAgo,
            int lastBarsAgo,
            TimeSpan offset)
        {
            return new
            {
                first_timestamp = Time[firstBarsAgo].ToString(
                    "yyyyMMdd HHmmss",
                    CultureInfo.InvariantCulture),
                last_timestamp = Time[lastBarsAgo].ToString(
                    "yyyyMMdd HHmmss",
                    CultureInfo.InvariantCulture),
                utc_offset = FormatOffset(offset)
            };
        }

        private IList<object> CaptureSessionCalendar(
            DateTime tradingDate,
            TimeZoneInfo applicationTimeZone)
        {
            List<object> segments = new List<object>();
            SessionIterator iterator = new SessionIterator(Bars);
            DateTime cursor = tradingDate.AddDays(-2);
            for (int attempt = 0; attempt < 10; attempt++)
            {
                iterator.GetNextSession(cursor, true);
                DateTime actualTradingDay = iterator.ActualTradingDayExchange.Date;
                if (actualTradingDay == tradingDate.Date)
                {
                    DateTime beginApplication = TimeZoneInfo.ConvertTime(
                        iterator.ActualSessionBegin,
                        TimeZoneInfo.Local,
                        applicationTimeZone);
                    DateTime endApplication = TimeZoneInfo.ConvertTime(
                        iterator.ActualSessionEnd,
                        TimeZoneInfo.Local,
                        applicationTimeZone);
                    segments.Add(new
                    {
                        begin_application = beginApplication.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture),
                        end_application = endApplication.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture),
                        begin_pc = iterator.ActualSessionBegin.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture),
                        end_pc = iterator.ActualSessionEnd.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture)
                    });
                }
                if (actualTradingDay > tradingDate.Date)
                    break;
                cursor = iterator.ActualSessionEnd.AddTicks(1);
            }
            if (segments.Count == 0)
                throw new InvalidOperationException(
                    "Applied Trading Hours produced no session for the selected trading date.");
            return new List<object>
            {
                new
                {
                    trading_date = tradingDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
                    segments = segments,
                    holiday_name = (string)null,
                    partial_holiday = (bool?)null,
                    effective_schedule_source = "SessionIterator using Bars.TradingHours"
                }
            };
        }

        private IList<object> CaptureActiveConnections()
        {
            List<object> result = new List<object>();
            foreach (Connection connection in Connection.Connections)
            {
                if (connection.Status != ConnectionStatus.Connected
                    && connection.PriceStatus != ConnectionStatus.Connected)
                    continue;
                result.Add(new
                {
                    name = ReadNestedString(connection, "Options", "Name"),
                    provider = ReadNestedString(connection, "Options", "Provider"),
                    status = connection.Status.ToString(),
                    price_status = connection.PriceStatus.ToString(),
                    instrument_types = connection.InstrumentTypes
                        .Select(value => value.ToString())
                        .ToArray()
                });
            }
            return result;
        }

        private static DateTime ReadDateTimeProperty(object value, string propertyName)
        {
            object result = ReadProperty(value, propertyName);
            if (!(result is DateTime))
                throw new InvalidOperationException(
                    "Required runtime property is unavailable: " + propertyName);
            return (DateTime)result;
        }

        private static string ReadNestedString(object value, params string[] propertyNames)
        {
            object current = value;
            foreach (string propertyName in propertyNames)
                current = ReadProperty(current, propertyName);
            if (current == null || string.IsNullOrWhiteSpace(current.ToString()))
                throw new InvalidOperationException(
                    "Required runtime property is unavailable: "
                    + string.Join(".", propertyNames));
            return current.ToString();
        }

        private static object ReadProperty(object value, string propertyName)
        {
            if (value == null)
                throw new InvalidOperationException(
                    "Required runtime property is unavailable: " + propertyName);
            System.Reflection.PropertyInfo property = value.GetType().GetProperty(propertyName);
            if (property == null)
                throw new InvalidOperationException(
                    "Required runtime property is unavailable: " + propertyName);
            return property.GetValue(value, null);
        }

        private static string FormatOffset(TimeSpan offset)
        {
            return string.Format(
                CultureInfo.InvariantCulture,
                "{0}{1:00}:{2:00}",
                offset < TimeSpan.Zero ? "-" : "+",
                Math.Abs(offset.Hours),
                Math.Abs(offset.Minutes));
        }

        private static string Sha256(string path)
        {
            using (SHA256 algorithm = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
                return string.Concat(
                    algorithm.ComputeHash(stream).Select(value => value.ToString("x2")));
        }

        private static string MakeSafeFileName(string value)
        {
            foreach (char invalidCharacter in Path.GetInvalidFileNameChars())
                value = value.Replace(invalidCharacter, '_');
            return value.Replace(' ', '_');
        }
    }
}
