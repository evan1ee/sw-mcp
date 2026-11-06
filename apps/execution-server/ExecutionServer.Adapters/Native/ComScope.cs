using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace ExecutionServer.Adapters.Native;

/// <summary>
/// Disposable scope for tracking and releasing temporary COM objects (enumerators, faces, edges, surfaces, math points).
/// Enforces Guideline G1 and ADR-059: releases temporary COM objects in reverse order.
/// Never releases ISldWorks, IModelDoc2, or manager objects.
/// Never calls Marshal.FinalReleaseComObject.
/// </summary>
public sealed class ComScope : IDisposable
{
    private readonly List<object> _objects = new List<object>();

    public T? Track<T>(T? comObject) where T : class
    {
        if (comObject != null && Marshal.IsComObject(comObject))
        {
            _objects.Add(comObject);
        }
        return comObject;
    }

    public void Dispose()
    {
        for (int i = _objects.Count - 1; i >= 0; i--)
        {
            var obj = _objects[i];
            try
            {
                if (Marshal.IsComObject(obj))
                {
                    Marshal.ReleaseComObject(obj);
                }
            }
            catch
            {
                // Best-effort cleanup
            }
        }
        _objects.Clear();
    }
}
