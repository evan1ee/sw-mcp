using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace PartChainSpike
{
    internal static partial class Program
    {
        private const double Mm = 0.001;
        private static readonly object EvLock = new object();
        private static readonly Stopwatch Clock = Stopwatch.StartNew();
        private static HashSet<string> _initialTitles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        private static void Ev(string s)
        {
            lock (EvLock) P($"    [event +{Clock.ElapsedMilliseconds}ms] {s}");
        }

        private static int _pid;
        internal static string Stage = "x";

        internal static bool Alive()
        {
            try { return !System.Diagnostics.Process.GetProcessById(_pid).HasExited; } catch { return false; }
        }

        private static void Step(string name, Action a)
        {
            P("");
            P("=== " + name + "   [stage " + Stage + "] (pid " + _pid + " alive=" + Alive() + ")");
            try { a(); }
            catch (Exception e) { P("  STEP FAILED: " + e.GetType().Name + ": " + e.Message); }
            bool alive = Alive();
            P("  -- step end; SOLIDWORKS pid " + _pid + " alive=" + alive);
            if (!alive) throw new InvalidOperationException("SOLIDWORKS exited during/after step: " + name);
        }

        private static T WithTimeout<T>(Func<T> f, int ms, out bool timedOut)
        {
            var t = Task.Run(f);
            timedOut = !t.Wait(ms);
            return timedOut ? default(T) : t.Result;
        }

        private static string Sha(string p)
        {
            using (var s = SHA256.Create()) using (var fs = new FileStream(p, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                return BitConverter.ToString(s.ComputeHash(fs)).Replace("-", "").Substring(0, 16);
        }

        private static string Hex(object o)
        {
            var b = o as byte[];
            return b == null ? "null" : $"{b.Length} bytes, head {BitConverter.ToString(b.Take(8).ToArray())}";
        }

        private static int _autoSave;

        /// <summary>
        /// The only way this spike closes anything, and always by exact full path under the work folder. A title is first resolved
        /// to a document that is open and was not open at the start; an unsaved one is saved into the work folder so it has a path.
        /// Anything else throws before touching SOLIDWORKS. CloseDoc is never called with a title.
        /// </summary>
        internal static void Close(string nameOrPath)
        {
            string path = nameOrPath;
            if (!Path.IsPathRooted(nameOrPath))
            {
                if (_initialTitles.Contains(nameOrPath)) throw new InvalidOperationException("refusing to close '" + nameOrPath + "': open at start");
                ModelDoc2 found = null;
                foreach (var o in (object[])Sw.GetDocuments() ?? new object[0])
                    if (((ModelDoc2)o).GetTitle() == nameOrPath) found = (ModelDoc2)o;
                if (found == null) { P("    (Close: no open document titled '" + nameOrPath + "')"); return; }
                path = found.GetPathName();
                if (string.IsNullOrEmpty(path))
                {
                    path = Path.Combine(Work, "autosave" + (++_autoSave) + ".SLDPRT");
                    int e, w;
                    if (!Save(found, path, out e, out w)) throw new InvalidOperationException("cannot give '" + nameOrPath + "' a path to close by, err=" + e);
                }
            }
            if (!path.StartsWith(Work, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("refusing to close outside the work folder: " + path);
            Sw.CloseDoc(path);
        }

        private static ModelDoc2 Open(string path, int options = (int)swOpenDocOptions_e.swOpenDocOptions_Silent)
        {
            int e = 0, w = 0;
            var d = (ModelDoc2)Sw.OpenDoc6(path, (int)swDocumentTypes_e.swDocPART, options, "", ref e, ref w);
            if (d == null) P($"    OpenDoc6 failed errors={e} warnings={w}");
            return d;
        }

        private static bool Save(ModelDoc2 d, string path, out int err, out int warn)
        {
            int e = 0, w = 0;
            bool ok = d.SaveAs4(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref e, ref w);
            err = e; warn = w;
            return ok;
        }

        private static int RunAll(string stage)
        {
            Stage = stage;
            _pid = Sw.GetProcessID();
            P($"SOLIDWORKS revision {Sw.RevisionNumber()}; pid {_pid}; document count at start: 0; stage {stage}");
            P("Work folder: " + Work);
            try
            {
                if (stage == "a")
                {
                    Step("A3 + A1 planes, sketch axes, extrude/cut directions", PlanesAndDirections);
                    Step("A2(before) A6 plate build, measure, GetID, save", PlateBuild);
                    Step("A4 templates and inch units", Templates);
                    Step("A9 calls on a non-active document", InactiveDoc);
                }
                else if (stage == "b")
                {
                    Step("A5 A8 A12 close and reopen the plate", PlateReopen);
                    Step("A7 CloseDoc with unsaved changes", DirtyClose);
                    Step("A10 SaveAs4 silent overwrite", Overwrite);
                }
                else if (stage == "c")
                {
                    Step("A13 part document events", PartEvents);
                    Step("A11 FileCloseNotify name format", CloseNotify);
                }
            }
            finally
            {
                if (Alive()) Cleanup(null);
                else P("SOLIDWORKS is not running; skipping cleanup");
            }
            return 0;
        }

        private static string _activeAtStart;

        /// <summary>Lists the open documents; aborts (false) if any already lives in the work folder, since that could be touched.</summary>
        internal static bool SnapshotAndGuard(bool strict)
        {
            int count = Sw.GetDocumentCount();
            if (strict && count != 0)
            {
                Console.Error.WriteLine("ABORT: GetDocumentCount=" + count + " (must be 0); nothing touched.");
                return false;
            }
            var titles = new List<string>();
            foreach (var o in (object[])Sw.GetDocuments() ?? new object[0])
            {
                var d = (ModelDoc2)o;
                titles.Add(d.GetTitle());
                string p = d.GetPathName() ?? "";
                if (p.StartsWith(Work, StringComparison.OrdinalIgnoreCase))
                {
                    Console.Error.WriteLine("ABORT: a document from the work folder is open already: " + p);
                    return false;
                }
            }
            _initialTitles = new HashSet<string>(titles, StringComparer.OrdinalIgnoreCase);
            var act = (ModelDoc2)Sw.ActiveDoc;
            _activeAtStart = act == null ? null : act.GetTitle();
            Console.WriteLine($"open documents ({titles.Count}): {string.Join(" | ", titles)}; active: {_activeAtStart}");
            return true;
        }

        private static void Cleanup(string activeAtStart)
        {
            P("");
            P("=== cleanup");
            foreach (var o in (object[])Sw.GetDocuments() ?? new object[0])
            {
                var d = (ModelDoc2)o;
                string t = d.GetTitle(), p = d.GetPathName() ?? "";
                bool mine = p.StartsWith(Work, StringComparison.OrdinalIgnoreCase) || !_initialTitles.Contains(t);
                if (mine) { P("  closing spike document " + t); Close(t); }
            }
            var left = ((object[])Sw.GetDocuments() ?? new object[0]).Select(x => ((ModelDoc2)x).GetTitle()).ToList();
            P($"  documents now open: [{string.Join(", ", left)}]; initial were [{string.Join(", ", _initialTitles)}]");
            ModelDoc2 cur;
            if (false && activeAtStart != null && (cur == null || cur.GetTitle() != activeAtStart))
            {
                int e = 0;
                Sw.ActivateDoc3(activeAtStart, false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref e);
                P($"  re-activated '{activeAtStart}' errors={e}");
            }
            P("  document count now: " + Sw.GetDocumentCount());
        }

        // ---------------- A3, A1 ----------------

        private static double[] Map(MathUtility mu, MathTransform t, double x, double y, double z)
        {
            var p = (MathPoint)mu.CreatePoint(new[] { x, y, z });
            var r = (MathPoint)p.MultiplyTransform(t);
            return (double[])r.ArrayData;
        }

        private static double[] Sub(double[] a, double[] b) { return new[] { a[0] - b[0], a[1] - b[1], a[2] - b[2] }; }

        private static void PlanesAndDirections()
        {
            var mu = (MathUtility)Sw.GetMathUtility();
            var names = new[] { "front?", "top?", "right?" };
            var scratch = NewPart(DefaultTemplate());
            var planes = RefPlanes(scratch);
            P($"  default template: '{DefaultTemplate()}'; RefPlane features in order: " + string.Join(" | ", planes.Select(p => p.Name)));
            for (int i = 0; i < planes.Count; i++)
            {
                var rp = (RefPlane)planes[i].GetSpecificFeature2();
                var tr = rp.Transform;
                var o = Map(mu, tr, 0, 0, 0);
                var z = Sub(Map(mu, tr, 0, 0, 1), o);
                P($"  A3 plane[{i}] name='{planes[i].Name}' Transform.ArrayData={Fmt((double[])tr.ArrayData)} origin={Fmt(o)} localZ(normal)={Fmt(z)} localX={Fmt(Sub(Map(mu, tr, 1, 0, 0), o))} localY={Fmt(Sub(Map(mu, tr, 0, 1, 0), o))}");
            }
            Close(scratch.GetTitle());

            for (int i = 0; i < Math.Min(3, planes.Count); i++)
            {
                var d = NewPart(DefaultTemplate());
                try
                {
                    var pl = RefPlanes(d)[i];
                    var sk = MakeSketch(d, pl, sm => Rect(sm, -20 * Mm, -10 * Mm, 20 * Mm, 10 * Mm));
                    var skObj = (Sketch)sk.GetSpecificFeature2();
                    var inv = (MathTransform)skObj.ModelToSketchTransform.Inverse();
                    var o = Map(mu, inv, 0, 0, 0);
                    var sx = Sub(Map(mu, inv, 1, 0, 0), o);
                    var sy = Sub(Map(mu, inv, 0, 1, 0), o);
                    var sz = Sub(Map(mu, inv, 0, 0, 1), o);
                    P($"  A1 sketch on '{pl.Name}' (RefPlane order {i}): sketch origin in model={Fmt(o)}; sketch +x -> model {Fmt(sx)}; sketch +y -> model {Fmt(sy)}; sketch +z (normal) -> model {Fmt(sz)}");
                    var ext = Extrude(d, sk, 10 * Mm);
                    var m0 = Measure(d);
                    P($"    blind extrude 10mm (Flip=false, Dir=false): feature={(ext == null ? "null" : ext.Name)}; vertexBox(m)={Fmt(m0.VertexBox)} volume_m3={m0.Volume:R}");
                    var cs = MakeSketch(d, pl, sm => sm.CreateCircleByRadius(0, 0, 0, 3 * Mm));
                    var cut = Cut(d, cs, 4 * Mm, false);
                    var m1 = Measure(d);
                    double dv = m1.Volume - m0.Volume;
                    P($"    blind cut 4mm r3mm (default direction): feature={(cut == null ? "null" : cut.Name)}; delta volume_m3={dv:R} (expected -{Math.PI * 9 * 4 * 1e-9:R} if it cuts into the body)");
                    if (cut == null || Math.Abs(dv) < 1e-15)
                    {
                        var cut2 = Cut(d, MakeSketch(d, pl, sm => sm.CreateCircleByRadius(0, 0, 0, 2 * Mm)), 4 * Mm, false, true, false);
                        var m2 = Measure(d);
                        P($"    default cut produced nothing (feature {(cut == null ? "null" : "created")}); flipped cut (Flip=true, Dir=false): feature={(cut2 == null ? "null" : cut2.Name)} delta volume_m3={m2.Volume - m1.Volume:R}");
                        var cut3 = Cut(d, MakeSketch(d, pl, sm => sm.CreateCircleByRadius(0, 0, 0, 1 * Mm)), 4 * Mm, false, false, true);
                        var m3 = Measure(d);
                        P($"    reversed-direction cut (Flip=false, Dir=true): feature={(cut3 == null ? "null" : cut3.Name)} delta volume_m3={m3.Volume - m2.Volume:R} (r1mm x 4mm would be -{Math.PI * 1 * 4 * 1e-9:R})");
                    }
                }
                finally { Close(d.GetTitle()); }
            }
        }

        // ---------------- plate pass: A2 A5 A6 A8 A11 A12 A13 ----------------

        private static void FeatureTable(ModelDoc2 d, string label, Dictionary<string, int> ids, Dictionary<string, byte[]> refs)
        {
            foreach (var f in AllFeatures(d))
            {
                string tn = f.GetTypeName2();
                if (true)
                {
                    int id = f.GetID();
                    var pr = d.Extension.GetPersistReference3(f) as byte[];
                    if (ids != null) ids[f.Name] = id;
                    if (refs != null && pr != null) refs[f.Name] = pr;
                    P($"    {label} feature '{f.Name}' type={tn} GetID={id} persistRef={Hex(pr)}");
                }
            }
        }

        private const double VolExp = (60000 - 4 * Math.PI * 16 * 10) * 1e-9;

        private static void PlateBuild()
        {
            string path = Path.Combine(Work, "plate1.SLDPRT");
            string other = Path.Combine(Work, "plate_noholes.SLDPRT");
            foreach (var f in new[] { path, other, path + ".renamed" }) if (File.Exists(f)) File.Delete(f);

            var d = NewPart(DefaultTemplate());
            var ids1 = new Dictionary<string, int>();
            var refs1 = new Dictionary<string, byte[]>();
            Feature sb, ex, sh;
            var cut = BuildPlate(d, RefPlanes(d)[0], out sb, out ex, out sh);
            P($"  plate features: {sb.Name}, {ex.Name}, {sh.Name}, {cut.Name}");
            d.ForceRebuild3(false);
            var m = Measure(d);
            double areaExp = (2 * 100 * 60 + 2 * (100 + 60) * 10 - 8 * Math.PI * 16 + 4 * 2 * Math.PI * 4 * 10) * 1e-6;
            P("  A6 measured: " + m.Text());
            P($"  A6 expected: volume_m3={VolExp:R} area_m2={areaExp:R} com_m=[0, 0, 0.005] box=[-0.05,-0.03,0, 0.05,0.03,0.01]");
            P($"  A6 differences: volume {m.Volume - VolExp:E3} m3; area {m.Area - areaExp:E3} m2; GetBodyBox vs vertex box max abs diff {m.BodyBox.Zip(m.VertexBox, (x, y) => Math.Abs(x - y)).Max():E3} m");
            var mpNo = d.Extension.CreateMassProperty();
            mpNo.UseSystemUnits = false;
            P($"  A6 UseSystemUnits=false: volume={mpNo.Volume:R} area={mpNo.SurfaceArea:R} (document units; template default)");
            FeatureTable(d, "before-close", ids1, refs1);
            File.WriteAllLines(Path.Combine(Work, "plate1_ids.txt"), ids1.Keys.Select(k => k + "|" + ids1[k] + "|" + (refs1.ContainsKey(k) ? Convert.ToBase64String(refs1[k]) : "")), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(Work, "plate1_volume.txt"), m.Volume.ToString("R"));

            int e, w;
            bool ok = Save(d, path, out e, out w);
            P($"  SaveAs4 silent ok={ok} err={e} warn={w}; title now '{d.GetTitle()}'; dirty(GetSaveFlag)={d.GetSaveFlag()}");
            Close(path);

            var d2 = NewPart(DefaultTemplate());
            Extrude(d2, MakeSketch(d2, RefPlanes(d2)[0], sm => Rect(sm, -50 * Mm, -30 * Mm, 50 * Mm, 30 * Mm)), 10 * Mm);
            Save(d2, other, out e, out w);
            P($"  saved no-holes sibling ok err={e}");
            Close(other);
        }

        private static void PlateReopen()
        {
            string path = Path.Combine(Work, "plate1.SLDPRT");
            string other = Path.Combine(Work, "plate_noholes.SLDPRT");
            if (!File.Exists(path) || !File.Exists(other)) { P("  stage a files missing; run stage a first"); return; }
            double volBefore = double.Parse(File.ReadAllText(Path.Combine(Work, "plate1_volume.txt")));
            var lines = File.ReadAllLines(Path.Combine(Work, "plate1_ids.txt")).Select(l => l.Split('|')).ToList();
            var ids1 = lines.ToDictionary(p => p[0], p => int.Parse(p[1]));
            var refs1 = lines.Where(p => p[2].Length > 0).ToDictionary(p => p[0], p => Convert.FromBase64String(p[2]));

            var first = Open(path);
            P($"  opened '{path}': {(first == null ? "FAILED" : "ok")}");
            var sw0 = Stopwatch.StartNew();
            Close(path);
            P($"  A12 CloseDoc(full path) returned after {sw0.ElapsedMilliseconds} ms");
            P($"  A12 GetOpenDocumentByName(path) right after CloseDoc returned: {(Sw.GetOpenDocumentByName(path) == null ? "null (reported closed)" : "STILL OPEN")}");
            LockTiming(path);

            var rd = Open(path);
            if (rd != null)
            {
                P($"  A12 reopened: title='{rd.GetTitle()}' path='{rd.GetPathName()}' dirty={rd.GetSaveFlag()}");
                var ids2 = new Dictionary<string, int>();
                var refs2 = new Dictionary<string, byte[]>();
                FeatureTable(rd, "after-reopen", ids2, refs2);
                foreach (var k in ids1.Keys)
                    P($"  A5 '{k}': GetID before={ids1[k]} after={(ids2.ContainsKey(k) ? ids2[k].ToString() : "missing")} => {(ids2.ContainsKey(k) && ids2[k] == ids1[k] ? "same" : "DIFFERENT")}");
                foreach (var k in refs1.Keys)
                {
                    bool same = refs2.ContainsKey(k) && refs1[k].SequenceEqual(refs2[k]);
                    int er = 0;
                    var obj = rd.Extension.GetObjectByPersistReference3(refs1[k], out er) as Feature;
                    P($"  A5 '{k}': persistRef bytes identical across reopen={same}; GetObjectByPersistReference3(old bytes) -> {(obj == null ? "null err=" + er : "feature '" + obj.Name + "' GetID=" + obj.GetID())}");
                }
                var m2 = Measure(rd);
                P("  A12 measure after reopen (no rebuild): " + m2.Text());
                P($"  A12 volume equal to pre-close (stage a value {volBefore:R}): {m2.Volume == volBefore} (diff {m2.Volume - volBefore:E3})");
                Close(path);
            }

            File.Copy(other, path, true);
            var rd2 = Open(path);
            if (rd2 != null)
            {
                var m3 = Measure(rd2);
                P($"  A12 replaced file on disk while closed, reopened: solids={m3.Solids} cylinders={m3.Cyl.Count} volume_m3={m3.Volume:R} (no-holes plate would be 6e-5) => reads from disk: {Math.Abs(m3.Volume - 6e-5) < 1e-9}");
                Close(path);
            }

            File.Copy(other, path, true);
            var ro = Open(path, (int)swOpenDocOptions_e.swOpenDocOptions_Silent | (int)swOpenDocOptions_e.swOpenDocOptions_ReadOnly);
            if (ro != null)
            {
                var m4 = Measure(ro);
                P($"  read-only open + measure: ReadOnly flag={ro.IsOpenedReadOnly()} dirty(GetSaveFlag)={ro.GetSaveFlag()} volume_m3={m4.Volume:R}");
                Close(path);
            }
        }

        private static void PartEvents()
        {
            string path = Path.Combine(Work, "ev_plate.SLDPRT");
            if (File.Exists(path)) File.Delete(path);
            var d = NewPart(DefaultTemplate());
            var pe = (DPartDocEvents_Event)(PartDoc)d;
            DPartDocEvents_RegenNotifyEventHandler r1 = () => { Ev("Part.RegenNotify"); return 0; };
            DPartDocEvents_RegenPostNotifyEventHandler r2 = () => { Ev("Part.RegenPostNotify"); return 0; };
            DPartDocEvents_FileSaveNotifyEventHandler s1 = n => { Ev($"Part.FileSaveNotify fileName='{n}'"); return 0; };
            DPartDocEvents_FileSavePostNotifyEventHandler s2 = (t, n) => { Ev($"Part.FileSavePostNotify saveType={t} fileName='{n}'"); return 0; };
            DPartDocEvents_DestroyNotifyEventHandler x1 = () => { Ev("Part.DestroyNotify"); return 0; };
            DPartDocEvents_DestroyNotify2EventHandler x2 = t => { Ev($"Part.DestroyNotify2 destroyType={t}"); return 0; };
            DPartDocEvents_AddItemNotifyEventHandler a1 = (t, n) => { Ev($"Part.AddItemNotify type={t} item='{n}'"); return 0; };
            DPartDocEvents_ModifyNotifyEventHandler m1 = () => { Ev("Part.ModifyNotify"); return 0; };
            pe.RegenNotify += r1; pe.RegenPostNotify += r2; pe.FileSaveNotify += s1; pe.FileSavePostNotify += s2;
            pe.DestroyNotify += x1; pe.DestroyNotify2 += x2; pe.AddItemNotify += a1; pe.ModifyNotify += m1;
            Feature sb, ex, sh;
            P("  -- building the plate (events come from FeatureExtrusion3 / FeatureCut4)");
            BuildPlate(d, RefPlanes(d)[0], out sb, out ex, out sh);
            P("  -- ForceRebuild3(false)");
            d.ForceRebuild3(false);
            P("  -- SaveAs4 silent");
            int e, w;
            Save(d, path, out e, out w);
            P("  -- CloseDoc(full path)");
            Close(path);
            Thread.Sleep(500);
            // subscriptions die with the document; no Unadvise on a closed document is attempted
        }

        // A8
        private static void LockTiming(string path)
        {
            string moved = path + ".renamed";
            var sw = Stopwatch.StartNew();
            int fails = 0;
            string lastErr = "";
            long okAt = -1;
            while (sw.ElapsedMilliseconds < 10000)
            {
                try { File.Move(path, moved); okAt = sw.ElapsedMilliseconds; break; }
                catch (IOException e) { fails++; lastErr = e.Message; Thread.Sleep(5); }
            }
            P($"  A8 rename right after CloseDoc returned: {(okAt >= 0 ? "succeeded after " + okAt + " ms and " + fails + " failed attempts" : "never within 10 s")}; last error: '{lastErr}'");
            if (okAt >= 0) File.Move(moved, path);

            // repeat 5 times with save->close->rename to get a distribution
            var times = new List<long>();
            for (int i = 0; i < 5; i++)
            {
                var d = NewPart(DefaultTemplate());
                var sk = MakeSketch(d, RefPlanes(d)[0], sm => Rect(sm, -0.01, -0.01, 0.01, 0.01));
                Extrude(d, sk, 0.005);
                string p = Path.Combine(Work, $"lock{i}.SLDPRT");
                if (File.Exists(p)) File.Delete(p);
                int e, w;
                Save(d, p, out e, out w);
                Close(d.GetTitle());
                var s2 = Stopwatch.StartNew();
                long t = -1;
                while (s2.ElapsedMilliseconds < 10000)
                {
                    try { File.Move(p, p + ".renamed"); t = s2.ElapsedMilliseconds; break; }
                    catch (IOException) { Thread.Sleep(5); }
                }
                times.Add(t);
            }
            P($"  A8 five save->close->rename trials, ms until rename succeeded (-1 = never in 10 s): [{string.Join(", ", times)}]");
        }

        // ---------------- A4 ----------------

        private static void Templates()
        {
            string raw = RawDefaultTemplatePref();
            string def = DefaultTemplate();
            P($"  swDefaultTemplatePart raw preference = '{raw}'; file exists={File.Exists(raw)}; template used for all other steps = '{def}'");
            bool toRaw;
            var rawDoc = WithTimeout(() => Sw.NewDocument(raw, 0, 0, 0), 15000, out toRaw);
            P($"  NewDocument(raw preference value) -> {(toRaw ? "TIMED OUT" : rawDoc == null ? "null" : "a document")}");
            if (rawDoc != null) Close(((ModelDoc2)rawDoc).GetTitle());
            P("  NOTE: the owner's preference was not cleared; the empty-preference case is exercised by passing the empty string, which is exactly what the API receives.");
            bool to;
            var r = WithTimeout(() => Sw.NewDocument("", (int)swDwgPaperSizes_e.swDwgPaperA4size, 0, 0), 15000, out to);
            P($"  NewDocument(\"\") -> {(to ? "TIMED OUT (dialog?)" : r == null ? "null" : "a document!")}");
            if (r != null) Close(((ModelDoc2)r).GetTitle());
            var bad = WithTimeout(() => Sw.NewDocument(Path.Combine(Work, "nope.prtdot"), 0, 0, 0), 15000, out to);
            P($"  NewDocument(nonexistent path) -> {(to ? "TIMED OUT" : bad == null ? "null" : "a document!")}");
            if (bad != null) Close(((ModelDoc2)bad).GetTitle());

            var d = NewPart(def);
            P($"  NewDocument(default template) -> {(d == null ? "null" : "doc '" + d.GetTitle() + "'")}");
            if (d == null) return;
            try
            {
                P($"  default template unit system={d.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitSystem, 0)} (1=CGS 2=MKS 3=IPS 4=MMGS) linear units={d.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0)}");
                P("  Only template found by file search: gb_part.prtdot and MBD/*.prtdot (all metric); no inch .prtdot is installed, so the inch case switches the new document's own unit system (document-level preference, not an application option).");
                bool setOk = d.Extension.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitSystem, 0, (int)swUnitSystem_e.swUnitSystem_IPS);
                P($"  SetUserPreferenceInteger(swUnitSystem, IPS) on the scratch doc -> {setOk}; reads back {d.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitSystem, 0)}; linear units now {d.Extension.GetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0)} (0=mm 2=inches)");
                Feature a, b, c;
                BuildPlate(d, RefPlanes(d)[0], out a, out b, out c);
                var m = Measure(d);
                double volExp = (60000 - 4 * Math.PI * 16 * 10) * 1e-9;
                P($"  inch-unit document, metres-based API: {m.Text()}");
                P($"  expected volume_m3={volExp:R}; diff {m.Volume - volExp:E3}; cylinders={m.Cyl.Count}");
                var mpNo = d.Extension.CreateMassProperty();
                mpNo.UseSystemUnits = false;
                P($"  mass property with UseSystemUnits=false in an inch document: volume={mpNo.Volume:R} (in^3 expected {volExp / 1.6387064e-5:R})");
            }
            finally { Close(d.GetTitle()); }
        }

        // ---------------- A7 ----------------

        private static void DirtyClose()
        {
            string p = Path.Combine(Work, "dirty.SLDPRT");
            bool timedOut;
            P("  never-saved dirty document: not tested; an unsaved document has no path, and the spike closes only by exact path under the work folder.");

            // (2) saved doc then modified, closed: does disk change?
            if (File.Exists(p)) File.Delete(p);
            var d2 = NewPart(DefaultTemplate());
            var sk = MakeSketch(d2, RefPlanes(d2)[0], sm => Rect(sm, -0.01, -0.01, 0.01, 0.01));
            Extrude(d2, sk, 0.005);
            int e, w;
            Save(d2, p, out e, out w);
            string hashBefore = Sha(p);
            Extrude(d2, MakeSketch(d2, RefPlanes(d2)[0], sm => Rect(sm, -0.005, -0.005, 0.005, 0.005)), 0.02);
            string t2 = d2.GetTitle();
            P($"  saved doc '{t2}' then added a feature: dirty={d2.GetSaveFlag()}");
            var sw2 = Stopwatch.StartNew();
            WithTimeout<int>(() => { Close(p); return 0; }, 20000, out timedOut);
            P($"  CloseDoc(full path of '{t2}') {(timedOut ? "DID NOT RETURN in 20 s (a prompt is likely open)" : "returned after " + sw2.ElapsedMilliseconds + " ms")}; still open={Sw.GetOpenDocumentByName(t2) != null}; file hash changed={Sha(p) != hashBefore} (false = unsaved changes were discarded)");
            P("  QuitDoc: not determined, unsafe on a live session (banned by the owner; never called).");
        }

        // ---------------- A9 ----------------

        private static void InactiveDoc()
        {
            string pa = Path.Combine(Work, "a9_a.SLDPRT");
            if (File.Exists(pa)) File.Delete(pa);
            var a = NewPart(DefaultTemplate());
            int e, w;
            Save(a, pa, out e, out w);
            string ta = a.GetTitle();
            var b = NewPart(DefaultTemplate());
            string tb = b.GetTitle();
            P($"  created A (saved as '{ta}') then B (unsaved '{tb}'); active now: {((ModelDoc2)Sw.ActiveDoc).GetTitle()}");
            foreach (var name in new[] { pa, ta, Path.GetFileNameWithoutExtension(ta), tb, tb + ".SLDPRT", tb + ".sldprt" })
                P($"  GetOpenDocumentByName('{name}') -> {(Sw.GetOpenDocumentByName(name) == null ? "null" : "found")}");
            var da = (ModelDoc2)Sw.GetOpenDocumentByName(pa);
            if (da == null) { P("  cannot reacquire A by path; stopping A9"); Close(tb); Close(ta); return; }
            try
            {
                var front = RefPlanes(da)[0];
                var sk = MakeSketch(da, front, sm => Rect(sm, -0.02, -0.02, 0.02, 0.02));
                P("  sketch on inactive doc A: OK (plane Select2, AddToDB, InsertSketch, CreateLine, FeatureByPositionReverse)");
                var ex = Extrude(da, sk, 0.01);
                P($"  FeatureExtrusion3 on inactive doc A: {(ex == null ? "returned null" : "OK, feature '" + ex.Name + "'")}");
                var cs = MakeSketch(da, front, sm => sm.CreateCircleByRadius(0, 0, 0, 0.005));
                var cut = Cut(da, cs, 0, true);
                P($"  FeatureCut4 through_all_both on inactive doc A: {(cut == null ? "returned null" : "OK, feature '" + cut.Name + "'")}");
                P("  measure on inactive doc A: " + Measure(da).Text());
                P($"  A dirty after edits={da.GetSaveFlag()}; ForceRebuild3 on inactive A -> {da.ForceRebuild3(false)}");
                bool ok = Save(da, pa, out e, out w);
                P($"  SaveAs4 (same path) on inactive A: ok={ok} err={e} warn={w}");
            }
            catch (Exception ex) { P("  call on inactive doc failed: " + ex.GetType().Name + ": " + ex.Message); }
            var act = (ModelDoc2)Sw.ActiveDoc;
            P($"  active document after the calls: '{(act == null ? "none" : act.GetTitle())}' (B was '{tb}'): calls did {(act != null && act.GetTitle() == tb ? "NOT " : "")}switch the active document");
            Close(tb);
            Close(ta);
        }

        // ---------------- A11 ----------------

        private static void CloseNotify()
        {
            var swEv = (DSldWorksEvents_Event)Sw;
            DSldWorksEvents_FileCloseNotifyEventHandler hClose = (n, r) => { Ev($"SW.FileCloseNotify fileName='{n}' reason={r}"); return 0; };
            DSldWorksEvents_DocumentLoadNotify2EventHandler hLoad = (t, p) => { Ev($"SW.DocumentLoadNotify2 title='{t}' path='{p}'"); return 0; };
            DSldWorksEvents_FileOpenPostNotifyEventHandler hOpen = n => { Ev($"SW.FileOpenPostNotify fileName='{n}'"); return 0; };
            swEv.DocumentLoadNotify2 += hLoad;
            swEv.FileOpenPostNotify += hOpen;
            swEv.FileCloseNotify += hClose;
            try
            {
                var d = NewPart(DefaultTemplate());
                string p = Path.Combine(Work, "a11_fullpath.SLDPRT");
                if (File.Exists(p)) File.Delete(p);
                int e, w;
                Save(d, p, out e, out w);
                P($"  -- CloseDoc('{p}')");
                Close(p);
                Thread.Sleep(700);
                P($"     still open={Sw.GetOpenDocumentByName(p) != null} (events above are all that fired)");
                P("  title-form and unsaved-document closes were not tried: the spike never calls CloseDoc with a title.");
            }
            finally
            {
                // only unsubscribe while SOLIDWORKS is alive; Unadvise on a dead server throws COMException
                if (Alive())
                {
                    try { swEv.FileCloseNotify -= hClose; swEv.DocumentLoadNotify2 -= hLoad; swEv.FileOpenPostNotify -= hOpen; }
                    catch (Exception ex) { P("  event unsubscribe failed: " + ex.GetType().Name); }
                }
            }
        }

        // ---------------- A10 ----------------

        private static void Overwrite()
        {
            string p = Path.Combine(Work, "overwrite.SLDPRT");
            if (File.Exists(p)) File.Delete(p);
            var d1 = NewPart(DefaultTemplate());
            Extrude(d1, MakeSketch(d1, RefPlanes(d1)[0], sm => Rect(sm, -0.01, -0.01, 0.01, 0.01)), 0.005);
            int e, w;
            bool ok1 = Save(d1, p, out e, out w);
            string h1 = Sha(p); long len1 = new FileInfo(p).Length;
            P($"  first SaveAs4 silent: ok={ok1} err={e} warn={w} size={len1} hash={h1}");
            Close(d1.GetTitle());

            var d2 = NewPart(DefaultTemplate());
            Extrude(d2, MakeSketch(d2, RefPlanes(d2)[0], sm => Rect(sm, -0.03, -0.02, 0.03, 0.02)), 0.02);
            bool ok2 = Save(d2, p, out e, out w);
            string h2 = Sha(p); long len2 = new FileInfo(p).Length;
            P($"  second SaveAs4 silent from a different doc to the EXISTING closed file: ok={ok2} err={e} (swFileSaveError_e) warn={w} size={len2} hash={h2} => overwritten={h1 != h2}");
            string t2 = d2.GetTitle();

            // target open in another doc
            var d3 = NewPart(DefaultTemplate());
            Extrude(d3, MakeSketch(d3, RefPlanes(d3)[0], sm => Rect(sm, -0.04, -0.04, 0.04, 0.04)), 0.03);
            bool ok3 = Save(d3, p, out e, out w);
            P($"  third SaveAs4 silent to a path that d2 currently has OPEN: ok={ok3} err={e} warn={w} hash now {Sha(p)} (changed={Sha(p) != h2})");
            Close(d3.GetTitle());
            Close(t2);
        }
    }
}
