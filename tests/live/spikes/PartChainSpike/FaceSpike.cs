using System;
using System.Collections.Generic;
using System.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace PartChainSpike
{
    /// <summary>
    /// Mode "face": throwaway spike for sketches on a face (plan 2026-11-06-face-reference-sketches, phase 0, K29).
    /// Answers: F1 which faces an extrude reports; F2 the sketch frame on its end and start faces across all three
    /// standard planes; F3/F4 which way a blind cut goes from each face for each Flip/Dir; F5 a through-all cut;
    /// F6 whether the end face is still one planar face after a hole is cut in it.
    /// Builds a 40 x 30 x 10 mm block in new documents only. Lengths in metres.
    /// </summary>
    internal static partial class Program
    {
        private static readonly (string Name, int Index, double[] Normal)[] StandardPlanes = new[]
        {
            ("plane:front", 0, new[] { 0.0, 0.0, 1.0 }),
            ("plane:top", 1, new[] { 0.0, 1.0, 0.0 }),
            ("plane:right", 2, new[] { 1.0, 0.0, 0.0 }),
        };

        private static int FaceSpikeRun()
        {
            Stage = "face";
            _pid = Sw.GetProcessID();
            P($"SOLIDWORKS revision {Sw.RevisionNumber()}; pid {_pid}; stage face");
            P("Work folder: " + Work);
            try
            {
                Step("F1 faces of the extrude", FaceInventory);
                Step("F2 sketch frame on the end face and the start face across all 3 planes", FaceSketchFrames);
                Step("F3 blind cut from the end face (top), each Flip/Dir", () => FaceBlindCuts("end"));
                Step("F4 blind cut from the start face (bottom), each Flip/Dir", () => FaceBlindCuts("start"));
                Step("F5 through-all cut from the end face", FaceThroughAll);
                Step("F6 end face after a hole is cut in it", FaceAfterHole);
            }
            finally
            {
                if (Alive()) Cleanup(null);
                else P("SOLIDWORKS is not running; skipping cleanup");
            }
            return 0;
        }

        private static Feature BuildBlock(out ModelDoc2 doc, int planeIndex = 0)
        {
            doc = NewPart(DefaultTemplate());
            var plane = RefPlanes(doc)[planeIndex];
            var sk = MakeSketch(doc, plane, sm => Rect(sm, -20 * Mm, -15 * Mm, 20 * Mm, 15 * Mm));
            var ext = Extrude(doc, sk, 10 * Mm);
            if (ext == null) throw new Exception("FeatureExtrusion3 returned null");
            return ext;
        }

        private static List<Face2> ExtrudeFaces(Feature ext)
        {
            var list = new List<Face2>();
            var raw = (object[])ext.GetFaces();
            if (raw != null) foreach (var o in raw) list.Add((Face2)o);
            return list;
        }

        private static string FaceInfo(Face2 f)
        {
            var s = (Surface)f.GetSurface();
            bool plane = s != null && s.IsPlane();
            string n = plane ? Fmt((double[])f.Normal) : "-";
            string root = plane ? Fmt(((double[])s.PlaneParams).Skip(3).Take(3).ToArray()) : "-";
            return $"planar={plane} outwardNormal={n} planeRoot={root} area_m2={f.GetArea():R} box={Fmt((double[])f.GetBox())}";
        }

        /// <summary>The planar face whose outward normal is along +baseNormal (end) or -baseNormal (start).</summary>
        private static Face2 PickFace(Feature ext, string which, double[]? baseNormal = null)
        {
            var bn = baseNormal ?? new[] { 0.0, 0.0, 1.0 };
            double sign = which == "end" ? 1.0 : -1.0;
            double wantX = sign * bn[0], wantY = sign * bn[1], wantZ = sign * bn[2];
            var found = ExtrudeFaces(ext).Where(f =>
            {
                var s = (Surface)f.GetSurface();
                if (s == null || !s.IsPlane()) return false;
                var n = (double[])f.Normal;
                return Math.Abs(n[0] - wantX) < 1e-9
                    && Math.Abs(n[1] - wantY) < 1e-9
                    && Math.Abs(n[2] - wantZ) < 1e-9;
            }).ToList();
            P($"    PickFace({which}): {found.Count} candidate(s)");
            if (found.Count != 1) throw new Exception("expected exactly one " + which + " face, got " + found.Count);
            return found[0];
        }

        private static void FaceInventory()
        {
            ModelDoc2 d;
            var ext = BuildBlock(out d);
            try
            {
                var faces = ExtrudeFaces(ext);
                P($"  extrude '{ext.Name}' reports {faces.Count} face(s)");
                for (int i = 0; i < faces.Count; i++) P($"  face[{i}] {FaceInfo(faces[i])}");
                PickFace(ext, "end");
                PickFace(ext, "start");
            }
            finally { Close(d.GetTitle()); }
        }

        /// <summary>Selects the face, opens a sketch on it, reports the sketch frame, and draws.</summary>
        private static Feature SketchOnFace(ModelDoc2 d, Face2 face, string label, Action<SketchManager> draw)
        {
            var mu = (MathUtility)Sw.GetMathUtility();
            var sm = d.SketchManager;
            var selMgr = (SelectionMgr)d.SelectionManager;
            var sd = (SelectData)selMgr.CreateSelectData();
            sd.Mark = 0;
            bool oldDb = sm.AddToDB, oldInf = sm.AutoInference;
            try
            {
                sm.AddToDB = true;
                sm.AutoInference = false;
                d.ClearSelection2(true);
                bool picked = ((Entity)face).Select4(false, sd);
                P($"    [{label}] Entity.Select4 -> {picked}; selected count={selMgr.GetSelectedObjectCount2(-1)}");
                if (!picked) throw new Exception("face Select4 failed");
                sm.InsertSketch(true);
                var active = sm.ActiveSketch;
                if (active == null) throw new Exception("no active sketch after InsertSketch on the face");
                var inv = (MathTransform)active.ModelToSketchTransform.Inverse();
                var o = Map(mu, inv, 0, 0, 0);
                P($"    [{label}] sketch origin in model={Fmt(o)}; +x -> {Fmt(Sub(Map(mu, inv, 1, 0, 0), o))}; +y -> {Fmt(Sub(Map(mu, inv, 0, 1, 0), o))}; +z (normal) -> {Fmt(Sub(Map(mu, inv, 0, 0, 1), o))}");
                draw(sm);
                sm.InsertSketch(true);
                var f = (Feature)d.FeatureByPositionReverse(0);
                if (f == null || f.GetTypeName2() != "ProfileFeature") throw new Exception("last feature is not a sketch");
                return f;
            }
            finally
            {
                sm.AddToDB = oldDb;
                sm.AutoInference = oldInf;
            }
        }

        private static void FaceSketchFrames()
        {
            foreach (var (planeName, planeIdx, baseNormal) in StandardPlanes)
            foreach (var which in new[] { "end", "start" })
            {
                ModelDoc2 d;
                var ext = BuildBlock(out d, planeIdx);
                try
                {
                    var face = PickFace(ext, which, baseNormal);
                    SketchOnFace(d, face, $"{planeName}/{which}_face", sm => sm.CreateCircleByRadius(10 * Mm, 5 * Mm, 0, 2.5 * Mm));
                    var cut = Cut(d, (Feature)d.FeatureByPositionReverse(0), 0, true);
                    var m = Measure(d);
                    P($"    [{planeName}/{which}_face] circle at sketch (10, 5) mm cut through all; cylinders (model, m):");
                    foreach (var c in m.Cyl) P("      point=" + Fmt(c.Take(3).ToArray()) + " dir=" + Fmt(c.Skip(3).Take(3).ToArray()) + " r=" + c[6].ToString("R"));
                }
                finally { Close(d.GetTitle()); }
            }
        }

        private static void FaceBlindCuts(string which)
        {
            foreach (var flip in new[] { false, true })
            foreach (var dir in new[] { false, true })
            {
                ModelDoc2 d;
                var ext = BuildBlock(out d);
                try
                {
                    var before = Measure(d);
                    var face = PickFace(ext, which);
                    var sk = SketchOnFace(d, face, $"{which}/flip={flip}/dir={dir}", sm => sm.CreateCircleByRadius(0, 0, 0, 2.5 * Mm));
                    var cut = Cut(d, sk, 4 * Mm, false, flip, dir);
                    var after = Measure(d);
                    double removed = before.Volume - after.Volume;
                    string zRange = "-";
                    foreach (var c in after.Cyl) zRange = "cylinder point=" + Fmt(c.Take(3).ToArray()) + " dir=" + Fmt(c.Skip(3).Take(3).ToArray());
                    var holeFace = cut == null ? null : ExtrudeFaces(cut).FirstOrDefault(f => ((Surface)f.GetSurface())?.IsCylinder() == true);
                    string wall = holeFace == null ? "no cylindrical face on the cut" : "hole wall box(m)=" + Fmt((double[])holeFace.GetBox());
                    P($"    {which} face, Flip={flip}, Dir={dir}: cut={(cut == null ? "null" : cut.Name)}; volume removed={removed:R} m3 (4 mm x r2.5 mm would be {Math.PI * 2.5 * 2.5 * 4 * 1e-9:R}); {zRange}; {wall}");
                }
                finally { Close(d.GetTitle()); }
            }
        }

        private static void FaceThroughAll()
        {
            ModelDoc2 d;
            var ext = BuildBlock(out d);
            try
            {
                var before = Measure(d);
                var sk = SketchOnFace(d, PickFace(ext, "end"), "end/through_all_both", sm => sm.CreateCircleByRadius(0, 0, 0, 2.5 * Mm));
                var cut = Cut(d, sk, 0, true);
                var after = Measure(d);
                P($"    through_all_both from the end face: cut={(cut == null ? "null" : cut.Name)}; removed={before.Volume - after.Volume:R} m3 (10 mm x r2.5 mm would be {Math.PI * 2.5 * 2.5 * 10 * 1e-9:R})");
            }
            finally { Close(d.GetTitle()); }
        }

        private static void FaceAfterHole()
        {
            ModelDoc2 d;
            var ext = BuildBlock(out d);
            try
            {
                var sk = SketchOnFace(d, PickFace(ext, "end"), "end/hole", sm => sm.CreateCircleByRadius(0, 0, 0, 2.5 * Mm));
                Cut(d, sk, 0, true);
                var faces = ExtrudeFaces(ext);
                int topFaces = faces.Count(f =>
                {
                    var s = (Surface)f.GetSurface();
                    return s != null && s.IsPlane() && Math.Abs(((double[])f.Normal)[2] - 1.0) < 1e-9;
                });
                P($"  after the hole: the extrude now reports {faces.Count} face(s); planar faces with outward normal +Z: {topFaces} (expect 1)");
                for (int i = 0; i < faces.Count; i++) P($"  face[{i}] {FaceInfo(faces[i])}");
            }
            finally { Close(d.GetTitle()); }
        }
    }
}
