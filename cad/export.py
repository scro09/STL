import cadquery as cq

def export_stl(model, filepath):
    cq.exporters.export(model, filepath)
    print(f"Exported STL to {filepath}")