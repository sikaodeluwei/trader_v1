// OFFLINE_TEST_ONLY. Deterministic inert NinjaTrader boundary fixtures.
// Compiles the actual exporter unchanged. No NinjaTrader assemblies or live data.
// TriggerCustomEvent uses a manually drained queue: it does not prove NT dispatch.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.Core
{
    public static class Globals
    {
        public static string UserDataDir;
        public static GeneralOptions GeneralOptions = new GeneralOptions();
    }
    public class GeneralOptions { public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time"); }
}
namespace NinjaTrader.Cbi
{
    public enum LogLevel { Information }
    public enum ConnectionStatus { Connected, Disconnected }
    public class MasterInstrument { public string Name = "MNQ"; }
    public class Instrument
    {
        public MasterInstrument MasterInstrument = new MasterInstrument();
        public DateTime Expiry { get { return new DateTime(2026, 9, 1); } }
        public string FullName = "MNQ SEP26 OFFLINE_TEST_ONLY";
        public string Exchange = "OFFLINE_TEST_ONLY";
    }
    public class ConnectionOptions
    {
        public string Name { get { return "OFFLINE_TEST_ONLY"; } }
        public string Provider { get { return "OFFLINE_TEST_ONLY"; } }
    }
    public class Connection
    {
        public static Connection[] Connections = { new Connection(), new Connection { Status = ConnectionStatus.Disconnected, PriceStatus = ConnectionStatus.Disconnected } };
        public ConnectionStatus Status = ConnectionStatus.Connected;
        public ConnectionStatus PriceStatus = ConnectionStatus.Connected;
        public ConnectionOptions Options { get { return new ConnectionOptions(); } }
        public string[] InstrumentTypes = { "Future" };
    }
}
namespace NinjaTrader.Data
{
    public enum BarsPeriodType { Minute }
    public class BarsPeriod { public BarsPeriodType BarsPeriodType = BarsPeriodType.Minute; public int Value = 5; }
    public class TradingHours
    {
        public string Name = "OFFLINE_TEST_ONLY";
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
    }
    public class Bars { public TradingHours TradingHours = new TradingHours(); }
    public class SessionIterator
    {
        private readonly Bars bars;
        public SessionIterator(Bars value) { bars = value; }
        public DateTime ActualTradingDayExchange { get; private set; }
        public DateTime ActualSessionBegin { get; private set; }
        public DateTime ActualSessionEnd { get; private set; }
        public DateTime GetTradingDay(DateTime timestamp)
        {
            return timestamp.Hour >= 17 ? timestamp.Date.AddDays(1) : timestamp.Date;
        }
        public void GetNextSession(DateTime cursor, bool include)
        {
            DateTime central = TimeZoneInfo.ConvertTime(cursor, TimeZoneInfo.Local, bars.TradingHours.TimeZoneInfo);
            DateTime day = central.Date.AddDays(1);
            ActualTradingDayExchange = day;
            ActualSessionBegin = TimeZoneInfo.ConvertTime(day.AddDays(-1).AddHours(17), bars.TradingHours.TimeZoneInfo, TimeZoneInfo.Local);
            ActualSessionEnd = TimeZoneInfo.ConvertTime(day.AddHours(16), bars.TradingHours.TimeZoneInfo, TimeZoneInfo.Local);
        }
    }
}
namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, DataLoaded, Historical, Realtime, Terminated }
    public enum Calculate { OnBarClose }
    public class NinjaScriptPropertyAttribute : Attribute { }
    public class Series<T>
    {
        public T[] Values;
        public T this[int ago] { get { return Values[Values.Length - 1 - ago]; } }
    }
    public class Indicator
    {
        private readonly Queue<Action> events = new Queue<Action>();
        public readonly List<string> Logs = new List<string>();
        public readonly List<Exception> Errors = new List<Exception>();
        public int MaxPending, MarketCallbacks, DispatchFailures;
        public ManualResetEvent DispatchEntered, ResumeDispatch;
        public State State;
        public string Description, Name;
        public Calculate Calculate;
        public bool IsOverlay;
        public int Count = 262, CurrentBar = 261;
        public NinjaTrader.Cbi.Instrument Instrument = new NinjaTrader.Cbi.Instrument();
        public NinjaTrader.Data.BarsPeriod BarsPeriod = new NinjaTrader.Data.BarsPeriod();
        public NinjaTrader.Data.Bars Bars = new NinjaTrader.Data.Bars();
        public Series<DateTime> Time = new Series<DateTime>();
        public Series<double> Open = new Series<double>(), High = new Series<double>(), Low = new Series<double>(), Close = new Series<double>();
        public Series<long> Volume = new Series<long>();
        public Indicator()
        {
            Time.Values = Enumerable.Range(0, Count).Select(i => new DateTime(2026, 6, 30, 17, 0, 0).AddMinutes(i * 5)).ToArray();
            Open.Values = Enumerable.Range(0, Count).Select(i => 100.0 + i).ToArray();
            High.Values = Open.Values.Select(i => i + 2).ToArray();
            Low.Values = Open.Values.Select(i => i - 1).ToArray();
            Close.Values = Open.Values.Select(i => i + 0.5).ToArray();
            Volume.Values = Enumerable.Range(0, Count).Select(i => (long)(1000 + i)).ToArray();
        }
        protected virtual void OnStateChange() { }
        protected virtual void OnBarUpdate() { }
        public void ChangeState(State value) { State = value; OnStateChange(); }
        public void Market() { Interlocked.Increment(ref MarketCallbacks); OnBarUpdate(); }
        public void Log(string message, NinjaTrader.Cbi.LogLevel level) { lock (Logs) Logs.Add(message); }
        public void Print(string message) { Console.WriteLine(message); }
        public void TriggerCustomEvent(Action<object> callback, object value)
        {
            if (DispatchEntered != null)
            {
                DispatchEntered.Set();
                if (!ResumeDispatch.WaitOne(4000)) throw new Exception("OFFLINE_TEST_ONLY dispatch barrier timed out");
            }
            if (DispatchFailures > 0) { Interlocked.Decrement(ref DispatchFailures); throw new InvalidOperationException("OFFLINE_TEST_ONLY dispatcher refusal"); }
            lock (events) { events.Enqueue(() => callback(value)); MaxPending = Math.Max(MaxPending, events.Count); }
        }
        public int Pending { get { lock (events) return events.Count; } }
        public void Drain()
        {
            Action action;
            lock (events) { if (events.Count == 0) return; action = events.Dequeue(); }
            try { action(); } catch (Exception error) { lock (Errors) Errors.Add(error); }
        }
    }
}
namespace NinjaTrader.NinjaScript.Indicators
{
    // Namespace-level fixture shadow redirects only the actual exporter's desktop
    // boundary. Production source is compiled as-is, never text rewritten.
    public static class Environment
    {
        public enum SpecialFolder { DesktopDirectory }
        public static string OfflineDesktop;
        public static ManualResetEvent PublicationEntered, ResumePublication;
        public static string NewLine { get { return System.Environment.NewLine; } }
        public static string GetFolderPath(SpecialFolder folder)
        {
            if (String.IsNullOrEmpty(OfflineDesktop) || !Path.GetFullPath(OfflineDesktop).StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("OFFLINE_TEST_ONLY desktop must be beneath system temp");
            if (PublicationEntered != null)
            {
                PublicationEntered.Set();
                if (!ResumePublication.WaitOne(4000)) throw new Exception("OFFLINE_TEST_ONLY publication barrier timed out");
            }
            return OfflineDesktop;
        }
    }
}
public static class ExporterBehavior
{
    private static string root;
    private static readonly List<ExportMnq5mCohortSource> instances = new List<ExportMnq5mCohortSource>();
    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new Exception("ASSERTION: " + message);
    }
    private static string Output(ExportMnq5mCohortSource exporter)
    {
        return Path.Combine(root, "desktop", "MNQ_5m_Acquisitions", exporter.AcquisitionId);
    }
    private static ExportMnq5mCohortSource Create(string id)
    {
        var e = new ExportMnq5mCohortSource();
        instances.Add(e);
        e.ChangeState(NinjaTrader.NinjaScript.State.SetDefaults);
        e.AcquisitionId = "OFFLINE_TEST_ONLY_" + id;
        e.CaseId = "OFFLINE_TEST_ONLY_case";
        e.CohortId = "OFFLINE_TEST_ONLY_cohort";
        e.TradingDateText = "2026-07-01";
        e.ArmFilePath = Path.Combine(root, e.AcquisitionId + ".arm");
        return e;
    }
    private static void Initialize(ExportMnq5mCohortSource e)
    {
        e.ChangeState(NinjaTrader.NinjaScript.State.DataLoaded);
        e.ChangeState(NinjaTrader.NinjaScript.State.Historical);
        e.ChangeState(NinjaTrader.NinjaScript.State.Realtime);
    }
    private static ExportMnq5mCohortSource TwoLifecyclePairs(bool blockDispatch)
    {
        var beforeRequest = Create("before_request");
        Initialize(beforeRequest);
        beforeRequest.ChangeState(NinjaTrader.NinjaScript.State.Terminated);
        var afterRequest = Create("after_request");
        // Publish both dispatch barriers before Realtime can start its timer.
        if (blockDispatch)
        {
            afterRequest.DispatchEntered = new ManualResetEvent(false);
            afterRequest.ResumeDispatch = new ManualResetEvent(false);
        }
        Initialize(afterRequest);
        Assert(instances.Sum(i => i.Logs.Count(x => x.Contains("exporter initialized event_time="))) == 2, "both initialized markers reached");
        Assert(instances.Sum(i => i.Logs.Count(x => x.Contains("realtime lifecycle observed event_time="))) == 2, "both Realtime markers reached");
        return afterRequest;
    }
    private static void Arm(ExportMnq5mCohortSource e, string text)
    {
        // Wait for natural filesystem time to advance; never mutate timestamps.
        Thread.Sleep(30);
        File.WriteAllText(e.ArmFilePath, text, new UTF8Encoding(false));
    }
    private static void Pump(ExportMnq5mCohortSource e, int milliseconds)
    {
        var clock = Stopwatch.StartNew();
        while (clock.ElapsedMilliseconds < milliseconds) { e.Drain(); Thread.Sleep(5); }
    }
    private static void ExpectError(Action action, string text)
    {
        try { action(); }
        catch (Exception error) { Assert(text == "IOException" ? error is IOException : error.Message.Contains(text), "expected " + text + ", got " + error); return; }
        throw new Exception("ASSERTION: expected rejection " + text);
    }
    private static void CheckBundle(ExportMnq5mCohortSource e)
    {
        string path = Output(e);
        Assert(File.Exists(Path.Combine(path, "runtime_capture.json")), "normal ExportBundle publishes runtime capture");
        Assert(Directory.GetFiles(path).Length == 4, "exact durable normal bundle files");
        Assert(e.Logs.Count(x => x.Contains(" export complete event_time=")) == 1, "exactly one durable normal export");
    }
    public static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        try
        {
            root = Path.GetFullPath(args[1]);
            Assert(root.StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase), "fixture output beneath system temp");
            Directory.CreateDirectory(root);
            NinjaTrader.NinjaScript.Indicators.Environment.OfflineDesktop = Path.Combine(root, "desktop");
            NinjaTrader.Core.Globals.UserDataDir = Path.Combine(root, "OFFLINE_TEST_ONLY_UserData");
            string templates = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "templates", "TradingHours");
            Directory.CreateDirectory(templates);
            File.WriteAllText(Path.Combine(templates, "OFFLINE_TEST_ONLY.xml"), "<OFFLINE_TEST_ONLY />");
            File.WriteAllText(Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "Config.xml"), "<OFFLINE_TEST_ONLY />");
            Console.WriteLine("OFFLINE_TEST_ONLY; real exporter normal paths; inert manually drained custom-event queue; NOT NinjaTrader runtime validation");
            string scenario = args[0];
            var e = TwoLifecyclePairs(scenario == "termination_dispatch");
            if (scenario == "stale")
            {
                e.ChangeState(NinjaTrader.NinjaScript.State.Terminated);
                e = Create("stale");
                Arm(e, e.AcquisitionId); Thread.Sleep(30); Initialize(e);
            }
            if (scenario == "termination_publication")
            {
                var entered = new ManualResetEvent(false);
                var resume = new ManualResetEvent(false);
                NinjaTrader.NinjaScript.Indicators.Environment.PublicationEntered = entered;
                NinjaTrader.NinjaScript.Indicators.Environment.ResumePublication = resume;
                Arm(e, e.AcquisitionId);
                var exportThread = new Thread(() => { try { e.Market(); } catch (Exception error) { lock (e.Errors) e.Errors.Add(error); } });
                var terminationDone = new ManualResetEvent(false);
                exportThread.Start();
                Assert(entered.WaitOne(2000), "actual normal ExportBundle reaches publication boundary");
                var terminateThread = new Thread(() => { e.ChangeState(NinjaTrader.NinjaScript.State.Terminated); terminationDone.Set(); });
                terminateThread.Start();
                bool disposedDuringPublication = terminationDone.WaitOne(100);
                resume.Set(); exportThread.Join(); terminateThread.Join();
                Assert(!disposedDuringPublication, "termination cleanup must serialize with actual normal publication");
                Pump(e, 500); CheckBundle(e);
                Assert(e.Errors.Count == 0 && e.Pending == 0, "termination/publication race leaves no queued work or publication error");
            }
            else if (scenario == "termination_dispatch")
            {
                Assert(e.DispatchEntered.WaitOne(2000), "raw poll reaches dispatcher boundary");
                e.ChangeState(NinjaTrader.NinjaScript.State.Terminated);
                Arm(e, e.AcquisitionId); e.ResumeDispatch.Set(); Pump(e, 600);
                Assert(!Directory.Exists(Output(e)) && e.Pending == 0, "late dispatched event after disposal is inert");
            }
            else if (scenario == "historical_pause")
            {
                Thread.Sleep(400);
                e.ChangeState(NinjaTrader.NinjaScript.State.Historical);
                Arm(e, e.AcquisitionId); Pump(e, 500);
                Assert(!Directory.Exists(Output(e)) && e.Pending == 0, "queued Realtime poll cannot export in Historical");
                e.ChangeState(NinjaTrader.NinjaScript.State.Realtime); Pump(e, 600); CheckBundle(e);
                Assert(e.MaxPending == 1, "Historical resume keeps bounded pending ownership");
            }
            else if (scenario == "historical_resume_pending")
            {
                Thread.Sleep(450);
                e.ChangeState(NinjaTrader.NinjaScript.State.Historical);
                Arm(e, e.AcquisitionId);
                e.ChangeState(NinjaTrader.NinjaScript.State.Realtime);
                Thread.Sleep(500);
                Assert(e.Pending == 1 && e.MaxPending == 1, "undrained event keeps its sole pending slot across resume");
                Pump(e, 600); CheckBundle(e);
            }
            else if (scenario == "dispatcher_refusal")
            {
                e.Drain(); e.DispatchFailures = 2;
                Arm(e, e.AcquisitionId); Pump(e, 1200); CheckBundle(e);
                Assert(e.MarketCallbacks == 0, "dispatcher refusal recovery needs no market callback");
            }
            else if (scenario == "no_lifecycle")
            {
                e.ChangeState(NinjaTrader.NinjaScript.State.Terminated);
                e = Create("no_lifecycle");
                e.ChangeState(NinjaTrader.NinjaScript.State.DataLoaded);
                e.ChangeState(NinjaTrader.NinjaScript.State.Historical);
                Arm(e, e.AcquisitionId); e.Market(); Pump(e, 350);
                Assert(!Directory.Exists(Output(e)), "historical arm cannot export");
                e.ChangeState(NinjaTrader.NinjaScript.State.Realtime); Pump(e, 600); CheckBundle(e);
            }
            else if (scenario == "missing" || scenario == "stale")
            {
                Pump(e, 400); e.Market();
                Assert(!Directory.Exists(Output(e)), "missing or stale arm does not export");
                Arm(e, e.AcquisitionId); Pump(e, 650); CheckBundle(e);
            }
            else if (scenario == "wrong_id" || scenario == "unreadable")
            {
                Arm(e, scenario == "wrong_id" ? "OFFLINE_TEST_ONLY_wrong" : e.AcquisitionId);
                FileStream held = scenario == "unreadable" ? new FileStream(e.ArmFilePath, FileMode.Open, FileAccess.Read, FileShare.None) : null;
                try
                {
                    Pump(e, 450);
                    ExpectError(() => e.Market(), scenario == "wrong_id" ? "exact AcquisitionId" : "IOException");
                    Assert(!Directory.Exists(Output(e)), "unaccepted arm causes no publication");
                }
                finally { if (held != null) held.Dispose(); }
                Arm(e, e.AcquisitionId); Pump(e, 650); CheckBundle(e);
                Assert(e.Errors.Count > 0, "queued handler preserves arm validation/read exception");
            }
            else if (scenario == "existing" || scenario == "partial")
            {
                if (scenario == "existing") { Directory.CreateDirectory(Output(e)); File.WriteAllText(Path.Combine(Output(e), "sentinel"), "OFFLINE_TEST_ONLY"); }
                else File.Delete(Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "Config.xml"));
                Arm(e, e.AcquisitionId);
                ExpectError(() => e.Market(), scenario == "existing" ? "refusing to overwrite" : "configuration file is unavailable");
                int errors = e.Errors.Count;
                for (int i = 0; i < 8; i++) e.Market();
                Pump(e, 450);
                Assert(e.Errors.Count == errors, "accepted/partial publication must never retry");
                Assert(e.Logs.Count(x => x.Contains(" export armed event_time=")) == 1, "accepted arm once");
                if (scenario == "existing") Assert(File.ReadAllText(Path.Combine(Output(e), "sentinel")) == "OFFLINE_TEST_ONLY", "existing output untouched");
                else Assert(File.Exists(Path.Combine(Output(e), "bars.txt")) && !File.Exists(Path.Combine(Output(e), "runtime_capture.json")), "normal path partial publication stays partial without retry");
            }
            else if (scenario == "terminate")
            {
                Thread.Sleep(450);
                Assert(e.Pending == 1, "one bounded poll queued before termination");
                e.ChangeState(NinjaTrader.NinjaScript.State.Terminated);
                Arm(e, e.AcquisitionId); Pump(e, 500); e.Market();
                Assert(!Directory.Exists(Output(e)) && e.Pending == 0, "termination disposes timer and makes queued event inert");
            }
            else if (scenario == "bounded")
            {
                Thread.Sleep(900);
                Assert(e.Pending == 1, "timer keeps at most one queued event");
                Arm(e, e.AcquisitionId); Pump(e, 500); CheckBundle(e);
                Assert(e.MaxPending == 1, "bounded queue under stalled dispatcher");
                Pump(e, 400); Assert(e.Pending == 0, "success disposes timer");
            }
            else if (scenario == "readiness")
            {
                e.CurrentBar = e.Count - 3;
                Arm(e, e.AcquisitionId); Pump(e, 400);
                Assert(!Directory.Exists(Output(e)), "timer preserves CurrentBar readiness");
                e.CurrentBar = e.Count - 1; Pump(e, 500); CheckBundle(e);
            }
            else
            {
                if (scenario == "poll_after_market") e.Market();
                Arm(e, e.AcquisitionId);
                if (scenario == "normal") e.Market();
                else if (scenario == "race")
                {
                    Thread.Sleep(300);
                    var start = new ManualResetEvent(false);
                    var threads = Enumerable.Range(0, 12).Select(i => new Thread(() => { start.WaitOne(); try { for (int n = 0; n < 4; n++) e.Market(); } catch (Exception error) { lock (e.Errors) e.Errors.Add(error); } })).ToArray();
                    foreach (var thread in threads) thread.Start();
                    start.Set(); e.Drain();
                    foreach (var thread in threads) thread.Join();
                    Assert(e.Errors.Count == 0, "simultaneous attempts must not double-publish or throw");
                }
                Pump(e, scenario == "late" ? 1250 : 450);
                if (scenario == "late")
                {
                    Assert(e.MarketCallbacks == 0, "ZERO post-arm market callbacks");
                    Assert(File.Exists(Path.Combine(Output(e), "runtime_capture.json")), "late arm must publish normal ExportBundle with ZERO post-arm market callbacks");
                }
                CheckBundle(e);
                if (scenario == "poll_after_market")
                    Assert(e.Logs.Count(x => x.Contains(" arm poll export completed realtime_bar_callbacks_since_initialized=1 ")) == 1, "poll diagnostic reports actual nonzero pre-arm callback count");
                if (scenario == "late")
                {
                    string diagnostic = e.Logs.SingleOrDefault(x => x.Contains(" arm poll export completed realtime_bar_callbacks_since_initialized=0 "));
                    Assert(diagnostic != null, "successful poll identifies trigger and ZERO Realtime callbacks since initialization");
                    Console.WriteLine(diagnostic);
                }
                if (scenario != "normal") for (int i = 0; i < 8; i++) { if (scenario != "late") e.Market(); e.Drain(); }
                Pump(e, 350); CheckBundle(e);
            }
            if (scenario != "wrong_id" && scenario != "unreadable")
                Assert(e.Errors.Count == 0, "no unexpected exporter custom-event errors");
            Console.WriteLine("PASS scenario=" + scenario + " market_callbacks=" + e.MarketCallbacks + " output=" + Output(e));
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        finally { foreach (var e in instances) e.ChangeState(NinjaTrader.NinjaScript.State.Terminated); }
    }
}
