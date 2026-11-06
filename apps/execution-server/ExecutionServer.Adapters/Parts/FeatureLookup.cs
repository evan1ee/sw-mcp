using System;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.Adapters.Parts;

/// <summary>Finds a feature by the <c>f&lt;id&gt;</c> handle the add-in returned (valid across close and reopen).</summary>
internal static class FeatureLookup
{
    public static IFeature? FindById(IModelDoc2 doc, string featureId)
    {
        if (string.IsNullOrWhiteSpace(featureId)) return null;

        string digits = featureId.StartsWith("f", StringComparison.OrdinalIgnoreCase) ? featureId.Substring(1) : featureId;
        if (!int.TryParse(digits, out int targetId)) return null;

        var feat = (IFeature?)doc.FirstFeature();
        while (feat != null)
        {
            if (feat.GetID() == targetId)
            {
                return feat;
            }

            feat = (IFeature?)feat.GetNextFeature();
        }

        return null;
    }
}
