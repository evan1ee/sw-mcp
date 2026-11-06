using System;

namespace ExecutionServer.Core.Parts;

/// <summary>
/// CAD-free unit conversions between IR units (mm, degrees) and SOLIDWORKS SI units (metres, radians),
/// and quantized rounding per spec 3.4.3 and 3.4.4.
/// </summary>
public static class PartUnits
{
    public const double DefaultLengthQuantumMm = 1e-6;
    public const double DefaultAngleQuantumDegrees = 1e-6;

    // --- Length -----------------------------------------------------------------------------

    public static double MmToMetres(double mm) => mm * 1e-3;

    public static double MetresToMm(double metres) => metres * 1e3;

    // --- Area -------------------------------------------------------------------------------

    public static double Mm2ToM2(double mm2) => mm2 * 1e-6;

    public static double M2ToMm2(double m2) => m2 * 1e6;

    // --- Volume -----------------------------------------------------------------------------

    public static double Mm3ToM3(double mm3) => mm3 * 1e-9;

    public static double M3ToMm3(double m3) => m3 * 1e9;

    // --- Angle ------------------------------------------------------------------------------

    public static double DegreesToRadians(double degrees) => degrees * (Math.PI / 180.0);

    public static double RadiansToDegrees(double radians) => radians * (180.0 / Math.PI);

    // --- Quantization and Comparison --------------------------------------------------------

    public static double Quantize(double value, double quantum)
    {
        if (quantum <= 0.0) return value;
        return Math.Round(value / quantum, MidpointRounding.AwayFromZero) * quantum;
    }

    public static double QuantizeLength(double mm, double quantum = DefaultLengthQuantumMm) =>
        Quantize(mm, quantum);

    public static double QuantizeAngle(double degrees, double quantum = DefaultAngleQuantumDegrees) =>
        Quantize(degrees, quantum);

    public static bool NearlyEqual(double a, double b, double tolerance) =>
        Math.Abs(a - b) <= tolerance;

    public static bool LengthEquals(double a, double b, double quantum = DefaultLengthQuantumMm) =>
        NearlyEqual(a, b, quantum);

    public static bool AngleEquals(double a, double b, double quantum = DefaultAngleQuantumDegrees) =>
        NearlyEqual(a, b, quantum);
}
