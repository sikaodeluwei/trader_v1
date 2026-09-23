#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

// Install this file as a NinjaTrader 8 indicator. Task 2 establishes only the
// scanner contract; Task 3 owns scan observations and all artifact output.
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
        private const string CanonicalizationId =
            "NINJATRADER_SEMICOLON_OHLCV_UTF8_LF_FINAL_NEWLINE_V1";
        private const string ActualTradingDayExchangeContract =
            nameof(SessionIterator.ActualTradingDayExchange);

        private bool armed;
        private DateTimeOffset initializedAtPc;
        private SessionIterator sessionIterator;

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
                Description = "Collects the MNQ SEP26 five-minute inventory contract.";
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
                Log(
                    "acquisition=" + AcquisitionId
                    + " inventory realtime lifecycle observed event_time="
                    + DateTimeOffset.Now.ToString("o", CultureInfo.InvariantCulture),
                    LogLevel.Information);
            }
        }

        protected override void OnBarUpdate()
        {
            // The contract remains inert until a fresh operator arm file exists.
            // Task 3 will add observation and artifact behavior after this gate.
            if (State != State.Realtime || armed || !TryArmScan())
                return;
        }

        private bool TryArmScan()
        {
            if (!File.Exists(ArmFilePath))
                return false;
            if (File.GetLastWriteTimeUtc(ArmFilePath) <= initializedAtPc.UtcDateTime)
                return false;
            if (File.ReadAllText(ArmFilePath).Trim() != AcquisitionId)
                throw new InvalidOperationException(
                    "Operator arm file must contain the exact AcquisitionId.");

            armed = true;
            Log(
                "acquisition=" + AcquisitionId
                + " inventory scan armed event_time="
                + DateTimeOffset.Now.ToString("o", CultureInfo.InvariantCulture),
                LogLevel.Information);
            return true;
        }

        // Task 3 invokes this only after durable inventory artifacts exist.
        private void LogScanComplete()
        {
            Log(
                "acquisition=" + AcquisitionId
                + " inventory scan complete event_time="
                + DateTimeOffset.Now.ToString("o", CultureInfo.InvariantCulture),
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
                || appliedTradingHours.Name != ApprovedTradingHoursName)
                throw new InvalidOperationException(
                    "Runtime Trading Hours must be CME US Index Futures ETH.");
        }

        private static DateTime ReadDateTimeProperty(object value, string propertyName)
        {
            if (value == null)
                throw new InvalidOperationException(
                    "Required runtime property is unavailable: " + propertyName);

            System.Reflection.PropertyInfo property = value.GetType().GetProperty(propertyName);
            if (property == null || !(property.GetValue(value, null) is DateTime))
                throw new InvalidOperationException(
                    "Required runtime property is unavailable: " + propertyName);
            return (DateTime)property.GetValue(value, null);
        }
    }
}
