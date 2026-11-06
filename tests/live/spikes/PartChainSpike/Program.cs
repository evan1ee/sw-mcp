using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace PartChainSpike
{
    /// <summary>
    /// Modes: "run" (all answers, default), "scratch" (make the A14 scratch part), "busy N" (keep SOLIDWORKS busy N seconds).
    /// Everything lives in %TEMP%\sw-mcp-spike\ and only documents this process creates are touched.
    /// </summary>
    internal static partial class Program
    {
        internal static readonly string Work = Path.Combine(Path.GetTempPath(), "sw-mcp-spike");
        internal static readonly StringBuilder Log = new StringBuilder();
        internal static ISldWorks Sw;
        internal static readonly List<string> Created = new List<string>();

        internal static void P(string line)
        {
            Console.WriteLine(line);
            Log.AppendLine(line);
            lock (Log) File.AppendAllText(Path.Combine(Work, "spike-output-" + Stage + ".txt"), line + System.Environment.NewLine, new UTF8Encoding(false));
        }

        [MTAThread]
        private static int Main(string[] args)
        {
            string mode = args.Length > 0 ? args[0] : "a";
            Console.OutputEncoding = new UTF8Encoding(false);
            Directory.CreateDirectory(Work);
            try
            {
                Sw = (ISldWorks)Marshal.GetActiveObject("SldWorks.Application");
            }
            catch (Exception e)
            {
                Console.Error.WriteLine("Cannot attach to running SOLIDWORKS: " + e.Message);
                return 2;
            }
            if (!SnapshotAndGuard(mode == "a" || mode == "b" || mode == "c")) return 3;
            Stage = mode;
            if (mode == "a" || mode == "b" || mode == "c") File.Delete(Path.Combine(Work, "spike-output-" + mode + ".txt"));
            switch (mode)
            {
                case "scratch": return MakeScratch();
                case "busy": return Busy(args.Length > 1 ? double.Parse(args[1]) : 10);
                case "face": return FaceSpikeRun();
                default: return RunAll(mode);
            }
        }

        // ---------- shared builders (all lengths in metres) ----------

        internal const string FallbackTemplate = @"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_part.prtdot";

        internal static string RawDefaultTemplatePref()
        {
            return Sw.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart);
        }

        /// <summary>The swDefaultTemplatePart preference when it names a real file, otherwise the installed metric gb_part.prtdot (see A4).</summary>
        internal static string DefaultTemplate()
        {
            string raw = RawDefaultTemplatePref();
            return !string.IsNullOrEmpty(raw) && File.Exists(raw) ? raw : FallbackTemplate;
        }

        internal static ModelDoc2 NewPart(string template)
        {
            var d = (ModelDoc2)Sw.NewDocument(template, 0, 0, 0);
            if (d != null) { Created.Add(d.GetTitle()); Console.WriteLine("  [created] " + d.GetTitle()); }
            return d;
        }

        internal static List<Feature> RefPlanes(ModelDoc2 d)
        {
            var l = new List<Feature>();
            for (var f = (Feature)d.FirstFeature(); f != null; f = (Feature)f.GetNextFeature())
                if (f.GetTypeName2() == "RefPlane") l.Add(f);
            return l;
        }

        internal static List<Feature> AllFeatures(ModelDoc2 d)
        {
            var l = new List<Feature>();
            for (var f = (Feature)d.FirstFeature(); f != null; f = (Feature)f.GetNextFeature()) l.Add(f);
            return l;
        }

        /// <summary>Opens a sketch on the plane with AddToDB and inference off, draws, closes, returns the sketch feature.</summary>
        internal static Feature MakeSketch(ModelDoc2 d, Feature plane, Action<SketchManager> draw)
        {
            var sm = d.SketchManager;
            bool oldDb = sm.AddToDB, oldInf = sm.AutoInference;
            try
            {
                sm.AddToDB = true;
                sm.AutoInference = false;
                d.ClearSelection2(true);
                if (!plane.Select2(false, 0)) throw new Exception("plane.Select2 failed");
                sm.InsertSketch(true);
                draw(sm);
                sm.InsertSketch(true);
                var f = (Feature)d.FeatureByPositionReverse(0);
                if (f == null || f.GetTypeName2() != "ProfileFeature") throw new Exception("last feature is not a sketch: " + (f == null ? "null" : f.GetTypeName2()));
                return f;
            }
            finally
            {
                sm.AddToDB = oldDb;
                sm.AutoInference = oldInf;
            }
        }

        internal static void Rect(SketchManager sm, double x0, double y0, double x1, double y1)
        {
            sm.CreateLine(x0, y0, 0, x1, y0, 0);
            sm.CreateLine(x1, y0, 0, x1, y1, 0);
            sm.CreateLine(x1, y1, 0, x0, y1, 0);
            sm.CreateLine(x0, y1, 0, x0, y0, 0);
        }

        /// <summary>FeatureExtrusion3 blind (or other end condition) from the selected sketch.</summary>
        internal static Feature Extrude(ModelDoc2 d, Feature sketch, double depth, bool flip = false, int endCond = 0)
        {
            d.ClearSelection2(true);
            if (!sketch.Select2(false, 0)) throw new Exception("sketch.Select2 failed");
            return (Feature)d.FeatureManager.FeatureExtrusion3(
                true, flip, false, endCond, 0, depth, 0.0,
                false, false, false, false, 0.0, 0.0,
                false, false, false, false,
                true, true, true,
                0, 0.0, false);
        }

        /// <summary>FeatureCut4 blind, or through_all_both when bothThrough is true.</summary>
        internal static Feature Cut(ModelDoc2 d, Feature sketch, double depth, bool bothThrough, bool flip = false, bool dir = false)
        {
            d.ClearSelection2(true);
            if (!sketch.Select2(false, 0)) throw new Exception("sketch.Select2 failed");
            int t = bothThrough ? (int)swEndConditions_e.swEndCondThroughAll : (int)swEndConditions_e.swEndCondBlind;
            return (Feature)d.FeatureManager.FeatureCut4(
                !bothThrough, flip, dir, t, bothThrough ? t : 0, depth, 0.0,
                false, false, false, false, 0.0, 0.0,
                false, false, false, false,
                false, true, true, false, false, false,
                0, 0.0, false, false);
        }

        internal static Feature BuildPlate(ModelDoc2 d, Feature front, out Feature sketchBase, out Feature extrude, out Feature sketchHoles, bool bothThrough = true)
        {
            double mm = 0.001;
            sketchBase = MakeSketch(d, front, sm => Rect(sm, -50 * mm, -30 * mm, 50 * mm, 30 * mm));
            extrude = Extrude(d, sketchBase, 10 * mm);
            if (extrude == null) throw new Exception("FeatureExtrusion3 returned null");
            sketchHoles = MakeSketch(d, front, sm =>
            {
                foreach (var c in new[] { new[] { -40.0, -20.0 }, new[] { 40.0, -20.0 }, new[] { 40.0, 20.0 }, new[] { -40.0, 20.0 } })
                    sm.CreateCircleByRadius(c[0] * mm, c[1] * mm, 0, 4 * mm);
            });
            var cut = Cut(d, sketchHoles, 0, bothThrough);
            if (cut == null) throw new Exception("FeatureCut4 returned null");
            return cut;
        }

        // ---------- measurement ----------

        internal sealed class Meas
        {
            public int Solids;
            public double[] BodyBox;
            public double[] VertexBox;
            public double Volume, Area;
            public double[] Com;
            public List<double[]> Cyl = new List<double[]>();
            public string Text()
            {
                var sb = new StringBuilder();
                sb.Append($"solids={Solids}; GetBodyBox={Fmt(BodyBox)}; vertexBox={Fmt(VertexBox)}; volume_m3={Volume:R}; area_m2={Area:R}; com_m={Fmt(Com)}");
                foreach (var c in Cyl) sb.Append("\n    cyl point=" + Fmt(c.Take(3).ToArray()) + " dir=" + Fmt(c.Skip(3).Take(3).ToArray()) + " r=" + c[6].ToString("R"));
                return sb.ToString();
            }
        }

        internal static string Fmt(double[] a)
        {
            return a == null ? "null" : "[" + string.Join(", ", a.Select(x => x.ToString("0.#########"))) + "]";
        }

        internal static Meas Measure(ModelDoc2 d, bool useSystemUnits = true)
        {
            var m = new Meas();
            var part = (PartDoc)d;
            var bodies = (object[])part.GetBodies2((int)swBodyType_e.swSolidBody, false);
            m.Solids = bodies == null ? 0 : bodies.Length;
            if (m.Solids > 0)
            {
                var body = (Body2)bodies[0];
                m.BodyBox = (double[])body.GetBodyBox();
                var vs = (object[])body.GetVertices();
                var lo = new[] { double.MaxValue, double.MaxValue, double.MaxValue };
                var hi = new[] { double.MinValue, double.MinValue, double.MinValue };
                if (vs != null)
                    foreach (Vertex v in vs)
                    {
                        var p = (double[])v.GetPoint();
                        for (int i = 0; i < 3; i++) { lo[i] = Math.Min(lo[i], p[i]); hi[i] = Math.Max(hi[i], p[i]); }
                    }
                m.VertexBox = lo.Concat(hi).ToArray();
                foreach (Face2 f in (object[])body.GetFaces())
                {
                    var s = (Surface)f.GetSurface();
                    if (s != null && s.IsCylinder())
                        m.Cyl.Add((double[])s.CylinderParams);
                }
            }
            var mp = d.Extension.CreateMassProperty();
            mp.UseSystemUnits = useSystemUnits;
            m.Volume = mp.Volume;
            m.Area = mp.SurfaceArea;
            m.Com = (double[])mp.CenterOfMass;
            return m;
        }

        // ---------- scratch/busy modes for test_live_a14.py ----------

        private static int MakeScratch()
        {
            string path = Path.Combine(Work, "a14_scratch.SLDPRT");
            if (File.Exists(path)) { P("scratch exists: " + path); return 0; }
            var d = NewPart(DefaultTemplate());
            string prev = Sw.ActiveDoc == null ? null : ((ModelDoc2)Sw.ActiveDoc).GetTitle();
            try
            {
                var front = RefPlanes(d)[0];
                var sk = MakeSketch(d, front, sm => Rect(sm, -0.05, -0.03, 0.05, 0.03));
                Extrude(d, sk, 0.01);
                int e = 0, w = 0;
                bool ok = d.SaveAs4(path, 0, 1, ref e, ref w);
                P($"scratch saved ok={ok} err={e} warn={w} path={path}");
                return ok ? 0 : 1;
            }
            finally
            {
                Close(d.GetTitle());
                Created.Clear();
            }
        }

        /// <summary>Holds SOLIDWORKS main thread busy with back-to-back rebuilds of a heavy scratch part.</summary>
        private static int Busy(double seconds)
        {
            var d = NewPart(DefaultTemplate());
            try
            {
                var front = RefPlanes(d)[0];
                double mm = 0.001;
                var sk = MakeSketch(d, front, sm => Rect(sm, -0.5, -0.5, 0.5, 0.5));
                Extrude(d, sk, 0.01);
                var holes = MakeSketch(d, front, sm =>
                {
                    for (int i = 0; i < 40; i++)
                        for (int j = 0; j < 40; j++)
                            sm.CreateCircleByRadius((-0.4875 + i * 0.025), (-0.4875 + j * 0.025), 0, 5 * mm);
                });
                Cut(d, holes, 0, true);
                P("busy: heavy part built, rebuilding for " + seconds + "s");
                var end = DateTime.UtcNow.AddSeconds(seconds);
                int n = 0;
                var sw = System.Diagnostics.Stopwatch.StartNew();
                while (DateTime.UtcNow < end) { d.Extension.ForceRebuildAll(); n++; }
                P($"busy: done, {n} rebuilds, {sw.Elapsed.TotalSeconds / Math.Max(n, 1):0.###}s each");
                return 0;
            }
            finally
            {
                Close(d.GetTitle());
            }
        }
    }
}
