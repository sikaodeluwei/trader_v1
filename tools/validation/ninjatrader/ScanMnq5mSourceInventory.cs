#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

// Install this file as a NinjaTrader 8 indicator. The scanner records only
// runtime, schedule, chronology, integrity, and identity facts.
namespace NinjaTrader.NinjaScript.Indicators
{
    public class ScanMnq5mSourceInventory : Indicator
    {
        private const string ApprovedContractLabel = "MNQ SEP26";
        private const int ApprovedExpiryMonth = 9;
        private const int ApprovedExpiryYear = 2026;
        private const string ApprovedRangeStart = "2026-06-22";
        private const string ApprovedRangeEnd = "2026-07-24";
        private const BarsPeriodType ApprovedBarsPeriodType = BarsPeriodType.Minute;
        private const int ApprovedBarsPeriodValue = 5;
        private const string ApprovedTradingHoursName = "CME US Index Futures ETH";
        private const string ScanFileName = "inventory_scan.json";
        private const string RuntimeFileName = "inventory_runtime_capture.json";
        private const string TradingHoursFileName = "trading_hours_template.xml";
        private const string ConfigFileName = "NinjaTrader.Config.xml";
        private const int ArmPollIntervalMilliseconds = 250;
        private const string CanonicalizationId =
            "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1";
        private const string ActualTradingDayExchangeContract =
            "ActualTradingDayExchange";

        private static readonly Encoding Utf8NoBom = new UTF8Encoding(false);

        private bool armed;
        private int armPollActive;
        private int armPollPending;
        private int exportStarted;
        private DateTimeOffset initializedAtPc;
        private DateTimeOffset realtimeAtPc;
        private DateTimeOffset armedAtPc;
        private SessionIterator sessionIterator;
        private System.Threading.Timer armPollTimer;

        [NinjaScriptProperty]
        [Display(Name = "Acquisition ID", Order = 1)]
        public string AcquisitionId { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Cohort ID", Order = 2)]
        public string CohortId { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Operator arm file", Order = 3)]
        public string ArmFilePath { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Output directory", Order = 4)]
        public string OutputDirectoryPath { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Collects facts for the MNQ SEP26 five-minute inventory.";
                Name = "ScanMnq5mSourceInventory";
                Calculate = Calculate.OnBarClose;
                IsOverlay = false;
                AcquisitionId = string.Empty;
                CohortId = "mnq-202609-5m-v1";
                ArmFilePath = string.Empty;
                OutputDirectoryPath = string.Empty;
            }
            else if (State == State.DataLoaded)
            {
                ValidateRuntimeSeries();
                sessionIterator = new SessionIterator(Bars);
                initializedAtPc = DateTimeOffset.Now;
                Log(
                    "acquisition=" + AcquisitionId
                    + " inventory scanner initialized event_time="
                    + initializedAtPc.ToString("o", CultureInfo.InvariantCulture),
                    LogLevel.Information);
            }
            else if (State == State.Realtime)
            {
                realtimeAtPc = DateTimeOffset.Now;
                Log(
                    "acquisition=" + AcquisitionId
                    + " inventory realtime lifecycle observed event_time="
                    + realtimeAtPc.ToString("o", CultureInfo.InvariantCulture),
                    LogLevel.Information);
                StartArmPolling();
            }
            else if (State == State.Terminated)
            {
                StopArmPolling();
            }
        }

        protected override void OnBarUpdate()
        {
            TryExportArmedAcquisition();
        }

        private void StartArmPolling()
        {
            if (armPollTimer != null)
                return;

            Interlocked.Exchange(ref armPollActive, 1);
            armPollTimer = new System.Threading.Timer(
                PollForArm,
                null,
                0,
                ArmPollIntervalMilliseconds);
        }

        private void StopArmPolling()
        {
            Interlocked.Exchange(ref armPollActive, 0);
            System.Threading.Timer timer = Interlocked.Exchange(ref armPollTimer, null);
            if (timer != null)
                timer.Dispose();
            Interlocked.Exchange(ref armPollPending, 0);
        }

        private void PollForArm(object state)
        {
            if (Interlocked.CompareExchange(ref armPollActive, 1, 1) != 1
                || Interlocked.CompareExchange(ref armPollPending, 1, 0) != 0)
                return;
            if (Interlocked.CompareExchange(ref armPollActive, 1, 1) != 1)
            {
                Interlocked.Exchange(ref armPollPending, 0);
                return;
            }

            TriggerCustomEvent(ProcessArmPoll, null);
        }

        private void ProcessArmPoll(object state)
        {
            try
            {
                TryExportArmedAcquisition();
            }
            finally
            {
                Interlocked.Exchange(ref armPollPending, 0);
            }
        }

        private void TryExportArmedAcquisition()
        {
            if (State != State.Realtime
                || armed
                || Interlocked.CompareExchange(ref exportStarted, 1, 0) != 0)
                return;

            if (!TryArmAcquisition())
            {
                Interlocked.Exchange(ref exportStarted, 0);
                return;
            }

            TimeZoneInfo applicationTimeZone = Core.Globals.GeneralOptions.TimeZoneInfo;
            if (applicationTimeZone == null)
                throw new InvalidOperationException(
                    "NinjaTrader application timezone is unavailable.");

            IList<object> activeConnections = CaptureActiveConnections();
            List<object> observations = new List<object>();
            foreach (DateTime civilDate in EnumerateCivilDates())
                observations.Add(CaptureSessionObservation(civilDate, applicationTimeZone));

            DateTimeOffset scanCompletedAtPc = DateTimeOffset.Now;
            object inventoryScan = BuildInventoryScan(
                observations,
                applicationTimeZone,
                scanCompletedAtPc);
            WriteBundleAtomically(
                inventoryScan,
                applicationTimeZone,
                scanCompletedAtPc,
                activeConnections);
            LogScanComplete();
            StopArmPolling();
        }

        private bool TryArmAcquisition()
        {
            if (!Path.IsPathRooted(ArmFilePath)
                || Path.GetExtension(ArmFilePath) != ".arm")
                throw new InvalidOperationException(
                    "Operator arm file must be an absolute path with the .arm extension.");
            if (!File.Exists(ArmFilePath))
                return false;
            if (File.GetLastWriteTimeUtc(ArmFilePath) <= initializedAtPc.UtcDateTime)
                throw new InvalidOperationException(
                    "Operator arm file is stale relative to scanner initialization.");
            if (File.ReadAllText(ArmFilePath).Trim() != AcquisitionId)
                throw new InvalidOperationException(
                    "Operator arm file must contain the exact AcquisitionId.");

            armedAtPc = DateTimeOffset.Now;
            armed = true;
            Log(
                "acquisition=" + AcquisitionId
                + " inventory scan armed event_time="
                + armedAtPc.ToString("o", CultureInfo.InvariantCulture),
                LogLevel.Information);
            return true;
        }

        private void LogScanComplete()
        {
            DateTimeOffset completedAtPc = DateTimeOffset.Now;
            Log(
                "acquisition=" + AcquisitionId
                + " inventory scan complete event_time="
                + completedAtPc.ToString("o", CultureInfo.InvariantCulture),
                LogLevel.Information);
        }

        private void ValidateRuntimeSeries()
        {
            if (string.IsNullOrWhiteSpace(AcquisitionId)
                || string.IsNullOrWhiteSpace(CohortId)
                || string.IsNullOrWhiteSpace(ArmFilePath)
                || string.IsNullOrWhiteSpace(OutputDirectoryPath)
                || !Path.IsPathRooted(ArmFilePath)
                || !Path.IsPathRooted(OutputDirectoryPath))
                throw new InvalidOperationException(
                    "AcquisitionId, CohortId, and absolute arm and output paths are required.");

            string finalOutputPath = OutputDirectoryPath.TrimEnd(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar);
            if (Directory.Exists(OutputDirectoryPath) || File.Exists(OutputDirectoryPath))
                throw new InvalidOperationException(
                    "The acquisition output path already exists; refusing to overwrite it.");
            if (Path.GetFileName(finalOutputPath) != MakeSafeFileName(AcquisitionId))
                throw new InvalidOperationException(
                    "The output directory name must equal the sanitized AcquisitionId.");

            DateTime expiry = ReadDateTimeProperty(Instrument, "Expiry");
            if (Instrument.MasterInstrument.Name != "MNQ"
                || expiry.Month != ApprovedExpiryMonth
                || expiry.Year != ApprovedExpiryYear)
                throw new InvalidOperationException(
                    "Runtime instrument is not the approved MNQ SEP26 contract.");

            if (BarsPeriod.BarsPeriodType != ApprovedBarsPeriodType
                || BarsPeriod.Value != ApprovedBarsPeriodValue)
                throw new InvalidOperationException(
                    "Runtime series must be native 5-minute Minute bars.");

            TradingHours appliedTradingHours = Bars.TradingHours;
            if (appliedTradingHours == null
                || appliedTradingHours.Name != ApprovedTradingHoursName
                || appliedTradingHours.TimeZoneInfo == null)
                throw new InvalidOperationException(
                    "Runtime Trading Hours must be CME US Index Futures ETH with timezone evidence.");
            if (appliedTradingHours.Holidays == null
                || appliedTradingHours.PartialHolidays == null)
                throw new InvalidOperationException(
                    "Runtime Trading Hours holiday evidence is unavailable.");
            if (Calculate != Calculate.OnBarClose)
                throw new InvalidOperationException(
                    "Runtime calculation mode must be OnBarClose.");
        }

        private static IList<DateTime> EnumerateCivilDates()
        {
            DateTime start = DateTime.ParseExact(
                ApprovedRangeStart,
                "yyyy-MM-dd",
                CultureInfo.InvariantCulture);
            DateTime end = DateTime.ParseExact(
                ApprovedRangeEnd,
                "yyyy-MM-dd",
                CultureInfo.InvariantCulture);
            if ((end - start).Days + 1 != 33)
                throw new InvalidOperationException(
                    "The approved inventory range must contain exactly 33 civil dates.");

            List<DateTime> result = new List<DateTime>();
            for (DateTime date = start; date <= end; date = date.AddDays(1))
                result.Add(date);
            return result;
        }

        private object CaptureSessionObservation(DateTime civilDate, TimeZoneInfo applicationTimeZone)
        {
            TradingHours appliedTradingHours = Bars.TradingHours;
            ScheduleMetadata scheduleMetadata = ResolveScheduleMetadata(
                appliedTradingHours,
                civilDate.Date);
            List<SessionSegment> segments = new List<SessionSegment>();
            SessionIterator iterator = new SessionIterator(Bars);
            DateTime cursor = civilDate.AddDays(-2);
            for (int attempt = 0; attempt < 32; attempt++)
            {
                iterator.GetNextSession(cursor, true);
                DateTime exchangeTradingDate = iterator.ActualTradingDayExchange.Date;
                if (exchangeTradingDate == civilDate.Date)
                {
                    segments.Add(CaptureSegment(
                        iterator.ActualSessionBegin,
                        iterator.ActualSessionEnd,
                        applicationTimeZone));
                }
                if (exchangeTradingDate > civilDate.Date)
                    break;
                cursor = iterator.ActualSessionEnd.AddTicks(1);
            }

            List<object> expectedOpenSegments = new List<object>();
            List<object> scheduledBreaks = new List<object>();
            foreach (SessionSegment segment in segments)
                expectedOpenSegments.Add(segment.ToEvidence());
            for (int index = 1; index < segments.Count; index++)
            {
                if (segments[index - 1].ApplicationEnd < segments[index].ApplicationBegin)
                {
                    scheduledBreaks.Add(new
                    {
                        begin_application = segments[index - 1].ApplicationEndOffset.ToString(
                            "o", CultureInfo.InvariantCulture),
                        end_application = segments[index].ApplicationBeginOffset.ToString(
                            "o", CultureInfo.InvariantCulture),
                        begin_pc = segments[index - 1].PcEndOffset.ToString(
                            "o", CultureInfo.InvariantCulture),
                        end_pc = segments[index].PcBeginOffset.ToString(
                            "o", CultureInfo.InvariantCulture)
                    });
                }
            }

            object scheduleEvidence = new
            {
                holiday_name = scheduleMetadata.HolidayName,
                partial_session = scheduleMetadata.PartialSession,
                expected_open_segments = expectedOpenSegments,
                scheduled_breaks = scheduledBreaks,
                application_session_begin = segments.Count == 0
                    ? null
                    : segments[0].ApplicationBeginOffset.ToString(
                        "o", CultureInfo.InvariantCulture),
                application_session_end = segments.Count == 0
                    ? null
                    : segments[segments.Count - 1].ApplicationEndOffset.ToString(
                        "o", CultureInfo.InvariantCulture),
                pc_log_session_begin = segments.Count == 0
                    ? null
                    : segments[0].PcBeginOffset.ToString("o", CultureInfo.InvariantCulture),
                pc_log_session_end = segments.Count == 0
                    ? null
                    : segments[segments.Count - 1].PcEndOffset.ToString(
                        "o", CultureInfo.InvariantCulture),
                effective_schedule_source =
                    "SessionIterator using Bars.TradingHours and ActualTradingDayExchange"
            };

            Dictionary<string, object> observation = new Dictionary<string, object>();
            observation.Add(
                "civil_date",
                civilDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
            if (segments.Count == 0)
            {
                observation.Add("classification", "NO_SESSION");
                observation.Add("exchange_trading_date", null);
                observation.Add("schedule_evidence", scheduleEvidence);
                observation.Add("quality", null);
                return observation;
            }

            observation.Add("classification", "SESSION");
            observation.Add(
                "exchange_trading_date",
                civilDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
            observation.Add("schedule_evidence", scheduleEvidence);
            observation.Add("quality", InspectSessionBars(segments));
            return observation;
        }

        private static ScheduleMetadata ResolveScheduleMetadata(
            TradingHours appliedTradingHours,
            DateTime exchangeTradingDate)
        {
            if (appliedTradingHours == null
                || appliedTradingHours.Holidays == null
                || appliedTradingHours.PartialHolidays == null)
                throw new InvalidOperationException(
                    "Runtime Trading Hours holiday evidence is unavailable.");

            string fullHolidayName;
            PartialHoliday partialHoliday;
            bool isFullHoliday = appliedTradingHours.Holidays.TryGetValue(
                exchangeTradingDate.Date,
                out fullHolidayName);
            bool isPartialSession = appliedTradingHours.PartialHolidays.TryGetValue(
                exchangeTradingDate.Date,
                out partialHoliday);
            if (isFullHoliday && isPartialSession)
                throw new InvalidOperationException(
                    "Runtime Trading Hours contains conflicting holiday evidence.");

            string holidayName = null;
            if (isPartialSession)
            {
                if (partialHoliday == null
                    || string.IsNullOrWhiteSpace(partialHoliday.Description))
                    throw new InvalidOperationException(
                        "Runtime Trading Hours partial-session evidence is incomplete.");
                holidayName = partialHoliday.Description;
            }
            else if (isFullHoliday)
            {
                if (string.IsNullOrWhiteSpace(fullHolidayName))
                    throw new InvalidOperationException(
                        "Runtime Trading Hours holiday evidence is incomplete.");
                holidayName = fullHolidayName;
            }

            return new ScheduleMetadata
            {
                HolidayName = holidayName,
                PartialSession = isPartialSession
            };
        }

        private object InspectSessionBars(IList<SessionSegment> segments)
        {
            List<BarFact> bars = new List<BarFact>();
            for (int index = 0; index < Bars.Count; index++)
            {
                DateTime timestamp = Bars.GetTime(index);
                if (!IsWithinSessionBounds(timestamp, segments))
                    continue;
                bars.Add(new BarFact
                {
                    SuppliedIndex = index,
                    Timestamp = timestamp,
                    Open = Bars.GetOpen(index),
                    High = Bars.GetHigh(index),
                    Low = Bars.GetLow(index),
                    Close = Bars.GetClose(index),
                    Volume = Convert.ToDouble(
                        Bars.GetVolume(index),
                        CultureInfo.InvariantCulture)
                });
            }

            List<DateTime> expectedTimestamps = EnumerateExpectedOpenTimestamps(segments);
            Dictionary<DateTime, int> observedCounts = new Dictionary<DateTime, int>();
            List<int> duplicateIndexes = new List<int>();
            List<int> decreasingIndexes = new List<int>();
            List<string> unexpectedTimestamps = new List<string>();
            List<int> malformedIndexes = new List<int>();
            List<int> invalidGeometryIndexes = new List<int>();
            List<int> negativeVolumeIndexes = new List<int>();
            List<int> nonIntegralVolumeIndexes = new List<int>();
            HashSet<DateTime> expectedSet = new HashSet<DateTime>(expectedTimestamps);

            DateTime? previousTimestamp = null;
            foreach (BarFact bar in bars)
            {
                int count;
                if (observedCounts.TryGetValue(bar.Timestamp, out count))
                {
                    observedCounts[bar.Timestamp] = count + 1;
                    duplicateIndexes.Add(bar.SuppliedIndex);
                }
                else
                {
                    observedCounts.Add(bar.Timestamp, 1);
                }
                if (previousTimestamp.HasValue && bar.Timestamp < previousTimestamp.Value)
                    decreasingIndexes.Add(bar.SuppliedIndex);
                previousTimestamp = bar.Timestamp;

                if (!expectedSet.Contains(bar.Timestamp))
                    unexpectedTimestamps.Add(FormatTimestamp(bar.Timestamp));
                if (!bar.HasFiniteOhlcv)
                    malformedIndexes.Add(bar.SuppliedIndex);
                if (bar.HasFiniteOhlcv
                    && (bar.Low > bar.High
                        || bar.Open < bar.Low
                        || bar.Open > bar.High
                        || bar.Close < bar.Low
                        || bar.Close > bar.High))
                    invalidGeometryIndexes.Add(bar.SuppliedIndex);
                if (IsFinite(bar.Volume) && bar.Volume < 0)
                    negativeVolumeIndexes.Add(bar.SuppliedIndex);
                if (IsFinite(bar.Volume) && bar.Volume != Math.Truncate(bar.Volume))
                    nonIntegralVolumeIndexes.Add(bar.SuppliedIndex);
                if (bar.HasFiniteOhlcv)
                    bar.CanonicalRow = CanonicalizeBar(bar);
            }

            List<string> missingExpectedTimestamps = new List<string>();
            foreach (DateTime expectedTimestamp in expectedTimestamps)
                if (!observedCounts.ContainsKey(expectedTimestamp))
                    missingExpectedTimestamps.Add(FormatTimestamp(expectedTimestamp));

            int validFromSessionStart = 0;
            while (validFromSessionStart < bars.Count
                && validFromSessionStart < expectedTimestamps.Count)
            {
                if (bars[validFromSessionStart].Timestamp
                    != expectedTimestamps[validFromSessionStart]
                    || !bars[validFromSessionStart].IsValidNativeBar)
                    break;
                validFromSessionStart++;
            }

            string first250Hash = null;
            if (bars.Count >= 250)
                first250Hash = Sha256CanonicalRows(
                    bars.Take(250).Select(value => value.CanonicalRow).ToList());

            string completeHash = null;
            if (bars.Count > 0 && bars.All(value => value.CanonicalRow != null))
                completeHash = Sha256CanonicalRows(
                    bars.Select(value => value.CanonicalRow).ToList());

            return new
            {
                observed_native_five_minute_bar_count = bars.Count,
                observed_valid_count_from_session_start = validFromSessionStart,
                first_observed_timestamp = bars.Count == 0
                    ? null
                    : FormatTimestamp(bars[0].Timestamp),
                two_hundred_fiftieth_native_timestamp = bars.Count < 250
                    ? null
                    : FormatTimestamp(bars[249].Timestamp),
                last_observed_session_timestamp = bars.Count == 0
                    ? null
                    : FormatTimestamp(bars[bars.Count - 1].Timestamp),
                supplied_order_strictly_increasing =
                    duplicateIndexes.Count == 0 && decreasingIndexes.Count == 0,
                duplicate_timestamp_indexes = duplicateIndexes,
                duplicate_timestamp_count = duplicateIndexes.Count,
                decreasing_timestamp_indexes = decreasingIndexes,
                decreasing_timestamp_count = decreasingIndexes.Count,
                missing_expected_open_timestamps = missingExpectedTimestamps,
                missing_expected_open_timestamp_count = missingExpectedTimestamps.Count,
                unexpected_timestamps = unexpectedTimestamps,
                unexpected_timestamp_count = unexpectedTimestamps.Count,
                malformed_or_non_finite_ohlcv_indexes = malformedIndexes,
                malformed_or_non_finite_ohlcv_count = malformedIndexes.Count,
                invalid_ohlc_geometry_indexes = invalidGeometryIndexes,
                invalid_ohlc_geometry_count = invalidGeometryIndexes.Count,
                negative_volume_indexes = negativeVolumeIndexes,
                negative_volume_count = negativeVolumeIndexes.Count,
                non_integral_volume_indexes = nonIntegralVolumeIndexes,
                non_integral_volume_count = nonIntegralVolumeIndexes.Count,
                first_250_source_sha256 = first250Hash,
                complete_session_source_sha256 = completeHash,
                canonicalization_id = CanonicalizationId
            };
        }

        private static string CanonicalizeBar(BarFact bar)
        {
            return string.Join(
                ";",
                bar.Timestamp.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture),
                bar.Open.ToString("R", CultureInfo.InvariantCulture),
                bar.High.ToString("R", CultureInfo.InvariantCulture),
                bar.Low.ToString("R", CultureInfo.InvariantCulture),
                bar.Close.ToString("R", CultureInfo.InvariantCulture),
                bar.Volume.ToString(CultureInfo.InvariantCulture));
        }

        private static string Sha256CanonicalRows(IList<string> rows)
        {
            if (rows == null || rows.Count == 0 || rows.Any(value => value == null))
                return null;
            byte[] bytes = new UTF8Encoding(false).GetBytes(
                string.Join("\n", rows) + "\n");
            using (SHA256 algorithm = SHA256.Create())
                return Hex(algorithm.ComputeHash(bytes));
        }

        private object BuildInventoryScan(IList<object> observations, TimeZoneInfo applicationTimeZone, DateTimeOffset completedAtPc)
        {
            DateTime expiry = ReadDateTimeProperty(Instrument, "Expiry");
            TradingHours appliedTradingHours = Bars.TradingHours;
            return new
            {
                schema_version = "1.0",
                acquisition_id = AcquisitionId,
                cohort_id = CohortId,
                contract = new
                {
                    contract_label = ApprovedContractLabel,
                    master_name = Instrument.MasterInstrument.Name,
                    full_name = Instrument.FullName,
                    expiry_month = expiry.Month,
                    expiry_year = expiry.Year
                },
                bar_series = new
                {
                    type = BarsPeriod.BarsPeriodType.ToString(),
                    value = BarsPeriod.Value,
                    native = true,
                    timestamp_semantics =
                        "NinjaTrader native Minute bar close timestamp in application time"
                },
                trading_hours = new
                {
                    name = appliedTradingHours.Name,
                    timezone_id = appliedTradingHours.TimeZoneInfo.Id,
                    exchange_trading_date_member = ActualTradingDayExchangeContract
                },
                civil_date_start = ApprovedRangeStart,
                civil_date_end = ApprovedRangeEnd,
                canonicalization_id = CanonicalizationId,
                observations = observations,
                transformations = new
                {
                    sorted = false,
                    deduplicated = false,
                    filled = false,
                    interpolated = false,
                    resampled = false,
                    timezone_converted = false,
                    back_adjusted = false,
                    repaired = false
                },
                completed_at = TimeZoneInfo.ConvertTime(
                    completedAtPc,
                    applicationTimeZone).ToString("o", CultureInfo.InvariantCulture)
            };
        }

        private void WriteBundleAtomically(object inventoryScan, TimeZoneInfo applicationTimeZone, DateTimeOffset completedAtPc, IList<object> activeConnections)
        {
            if (Directory.Exists(OutputDirectoryPath) || File.Exists(OutputDirectoryPath))
                throw new InvalidOperationException(
                    "The acquisition output path already exists; refusing to overwrite it.");

            string userData = Core.Globals.UserDataDir;
            string tradingHoursSource = Path.Combine(
                userData,
                "templates",
                "TradingHours",
                Bars.TradingHours.Name + ".xml");
            string configSource = Path.Combine(userData, "Config.xml");
            if (!File.Exists(tradingHoursSource) || !File.Exists(configSource))
                throw new InvalidOperationException(
                    "Trading Hours template or NinjaTrader configuration file is unavailable.");

            string parentDirectory = Path.GetDirectoryName(OutputDirectoryPath);
            if (string.IsNullOrWhiteSpace(parentDirectory)
                || !Directory.Exists(parentDirectory))
                throw new InvalidOperationException(
                    "The output parent directory must already exist.");
            string stagingDirectory = Path.Combine(
                parentDirectory,
                "." + Path.GetFileName(OutputDirectoryPath)
                + ".partial-" + Guid.NewGuid().ToString("N"));
            bool published = false;
            try
            {
                Directory.CreateDirectory(stagingDirectory);

                string scanPath = Path.Combine(stagingDirectory, ScanFileName);
                string runtimePath = Path.Combine(stagingDirectory, RuntimeFileName);
                string tradingHoursDestination = Path.Combine(
                    stagingDirectory,
                    TradingHoursFileName);
                string configDestination = Path.Combine(stagingDirectory, ConfigFileName);

                File.Copy(tradingHoursSource, tradingHoursDestination, false);
                File.Copy(configSource, configDestination, false);
                WriteJsonAtomically(
                    scanPath,
                    new JavaScriptSerializer().Serialize(inventoryScan));

                string scanHash = Sha256File(scanPath);
                string tradingHoursHash = Sha256File(tradingHoursDestination);
                string configHash = Sha256File(configDestination);
                object runtimeCapture = BuildRuntimeCapture(
                    applicationTimeZone,
                    completedAtPc,
                    scanHash,
                    tradingHoursHash,
                    configHash,
                    activeConnections);
                WriteJsonAtomically(
                    runtimePath,
                    new JavaScriptSerializer().Serialize(runtimeCapture));

                VerifyPublishedBundle(stagingDirectory);
                Directory.Move(stagingDirectory, OutputDirectoryPath);
                VerifyPublishedBundle(OutputDirectoryPath);
                published = true;
            }
            finally
            {
                if (!published && Directory.Exists(stagingDirectory))
                    Directory.Delete(stagingDirectory, true);
            }
        }

        private static void VerifyPublishedBundle(string directory)
        {
            foreach (string requiredPath in new[]
            {
                Path.Combine(directory, ScanFileName),
                Path.Combine(directory, RuntimeFileName),
                Path.Combine(directory, TradingHoursFileName),
                Path.Combine(directory, ConfigFileName)
            })
                if (!File.Exists(requiredPath))
                    throw new InvalidOperationException(
                        "The inventory bundle is incomplete.");
            if (Directory.GetFiles(directory).Length != 4)
                throw new InvalidOperationException(
                    "The inventory bundle contains an unexpected artifact.");
        }

        private object BuildRuntimeCapture(TimeZoneInfo applicationTimeZone, DateTimeOffset completedAtPc, string scanHash, string tradingHoursHash, string configHash, IList<object> activeConnections)
        {
            TimeZoneInfo pcTimeZone = TimeZoneInfo.Local;
            DateTime expiry = ReadDateTimeProperty(Instrument, "Expiry");
            return new
            {
                schema_version = "1.0",
                acquisition_id = AcquisitionId,
                cohort_id = CohortId,
                instrument = new
                {
                    contract_label = ApprovedContractLabel,
                    full_name = Instrument.FullName,
                    master_name = Instrument.MasterInstrument.Name,
                    expiry_month = expiry.Month,
                    expiry_year = expiry.Year
                },
                ninjatrader_version =
                    typeof(Instrument).Assembly.GetName().Version.ToString(),
                scanner_identity = new
                {
                    name = Name,
                    scanner_sha256 = (string)null,
                    scanner_sha256_recording_authority = "operator/finalizer"
                },
                bar_series = new
                {
                    type = BarsPeriod.BarsPeriodType.ToString(),
                    value = BarsPeriod.Value,
                    native = true,
                    calculate = Calculate.ToString()
                },
                trading_hours = new
                {
                    name = Bars.TradingHours.Name,
                    timezone_id = Bars.TradingHours.TimeZoneInfo.Id
                },
                application_timezone = CaptureTimeZone(applicationTimeZone),
                pc_timezone = CaptureTimeZone(pcTimeZone),
                active_connections = activeConnections,
                connection_snapshot_phase =
                    "immediately after operator arm and before inventory scan",
                lifecycle = new
                {
                    initialized_at = initializedAtPc.ToString(
                        "o", CultureInfo.InvariantCulture),
                    realtime_observed_at = realtimeAtPc.ToString(
                        "o", CultureInfo.InvariantCulture),
                    armed_at = armedAtPc.ToString("o", CultureInfo.InvariantCulture),
                    completed_at = completedAtPc.ToString(
                        "o", CultureInfo.InvariantCulture)
                },
                artifact_hashes = new
                {
                    inventory_scan = new
                    {
                        file_name = ScanFileName,
                        sha256 = scanHash
                    },
                    inventory_runtime_capture = new
                    {
                        file_name = RuntimeFileName,
                        sha256 = (string)null,
                        sha256_recording_authority = "operator/finalizer"
                    },
                    trading_hours_template = new
                    {
                        file_name = TradingHoursFileName,
                        sha256 = tradingHoursHash
                    },
                    ninjatrader_config = new
                    {
                        file_name = ConfigFileName,
                        sha256 = configHash
                    }
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

        private static void WriteJsonAtomically(string finalPath, string json)
        {
            if (File.Exists(finalPath))
                throw new InvalidOperationException(
                    "Refusing to overwrite an existing inventory JSON artifact.");
            string temporaryPath = finalPath + ".tmp";
            File.WriteAllText(temporaryPath, json + "\n", Utf8NoBom);
            File.Move(temporaryPath, finalPath);
        }

        private static SessionSegment CaptureSegment(DateTime pcBegin, DateTime pcEnd, TimeZoneInfo applicationTimeZone)
        {
            DateTimeOffset pcBeginOffset = AttachOffset(pcBegin, TimeZoneInfo.Local);
            DateTimeOffset pcEndOffset = AttachOffset(pcEnd, TimeZoneInfo.Local);
            DateTimeOffset applicationBeginOffset = TimeZoneInfo.ConvertTime(
                pcBeginOffset,
                applicationTimeZone);
            DateTimeOffset applicationEndOffset = TimeZoneInfo.ConvertTime(
                pcEndOffset,
                applicationTimeZone);
            return new SessionSegment
            {
                ApplicationBegin = applicationBeginOffset.DateTime,
                ApplicationEnd = applicationEndOffset.DateTime,
                ApplicationBeginOffset = applicationBeginOffset,
                ApplicationEndOffset = applicationEndOffset,
                PcBeginOffset = pcBeginOffset,
                PcEndOffset = pcEndOffset
            };
        }

        private static DateTimeOffset AttachOffset(DateTime value, TimeZoneInfo timeZone)
        {
            DateTime unspecified = DateTime.SpecifyKind(value, DateTimeKind.Unspecified);
            return new DateTimeOffset(unspecified, timeZone.GetUtcOffset(unspecified));
        }

        private static bool IsWithinSessionBounds(DateTime timestamp, IList<SessionSegment> segments)
        {
            return segments.Count > 0
                && timestamp > segments[0].ApplicationBegin
                && timestamp <= segments[segments.Count - 1].ApplicationEnd;
        }

        private static List<DateTime> EnumerateExpectedOpenTimestamps(IList<SessionSegment> segments)
        {
            List<DateTime> result = new List<DateTime>();
            foreach (SessionSegment segment in segments)
                for (DateTime timestamp = segment.ApplicationBegin.AddMinutes(5);
                    timestamp <= segment.ApplicationEnd;
                    timestamp = timestamp.AddMinutes(5))
                    result.Add(timestamp);
            return result;
        }

        private static bool IsFinite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static string FormatTimestamp(DateTime value)
        {
            return value.ToString("yyyyMMdd HHmmss", CultureInfo.InvariantCulture);
        }

        private static object CaptureTimeZone(TimeZoneInfo timeZone)
        {
            return new
            {
                id = timeZone.Id,
                display_name = timeZone.DisplayName,
                standard_name = timeZone.StandardName,
                daylight_name = timeZone.DaylightName,
                base_utc_offset = FormatOffset(timeZone.BaseUtcOffset),
                supports_dst = timeZone.SupportsDaylightSavingTime
            };
        }

        private static string Sha256File(string path)
        {
            using (SHA256 algorithm = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
                return Hex(algorithm.ComputeHash(stream));
        }

        private static string Hex(byte[] bytes)
        {
            StringBuilder result = new StringBuilder(bytes.Length * 2);
            foreach (byte value in bytes)
                result.Append(value.ToString("x2", CultureInfo.InvariantCulture));
            return result.ToString();
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

        private static string MakeSafeFileName(string value)
        {
            foreach (char invalidCharacter in Path.GetInvalidFileNameChars())
                value = value.Replace(invalidCharacter, '_');
            return value.Replace(' ', '_');
        }

        private sealed class SessionSegment
        {
            public DateTime ApplicationBegin { get; set; }
            public DateTime ApplicationEnd { get; set; }
            public DateTimeOffset ApplicationBeginOffset { get; set; }
            public DateTimeOffset ApplicationEndOffset { get; set; }
            public DateTimeOffset PcBeginOffset { get; set; }
            public DateTimeOffset PcEndOffset { get; set; }

            public object ToEvidence()
            {
                return new
                {
                    begin_application = ApplicationBeginOffset.ToString(
                        "o", CultureInfo.InvariantCulture),
                    end_application = ApplicationEndOffset.ToString(
                        "o", CultureInfo.InvariantCulture),
                    begin_pc = PcBeginOffset.ToString("o", CultureInfo.InvariantCulture),
                    end_pc = PcEndOffset.ToString("o", CultureInfo.InvariantCulture)
                };
            }
        }

        private sealed class ScheduleMetadata
        {
            public string HolidayName { get; set; }
            public bool PartialSession { get; set; }
        }

        private sealed class BarFact
        {
            public int SuppliedIndex { get; set; }
            public DateTime Timestamp { get; set; }
            public double Open { get; set; }
            public double High { get; set; }
            public double Low { get; set; }
            public double Close { get; set; }
            public double Volume { get; set; }
            public string CanonicalRow { get; set; }

            public bool HasFiniteOhlcv
            {
                get
                {
                    return IsFinite(Open)
                        && IsFinite(High)
                        && IsFinite(Low)
                        && IsFinite(Close)
                        && IsFinite(Volume);
                }
            }

            public bool IsValidNativeBar
            {
                get
                {
                    return HasFiniteOhlcv
                        && Low <= High
                        && Open >= Low
                        && Open <= High
                        && Close >= Low
                        && Close <= High
                        && Volume >= 0
                        && Volume == Math.Truncate(Volume)
                        && CanonicalRow != null;
                }
            }
        }
    }
}
