import cadquery as cq

def generate_ring(finger_radius, band_width, wall_thickness):
    outer_radius = finger_radius + wall_thickness

    ring = (
        cq.Workplane("XY")
        .circle(outer_radius)
        .circle(finger_radius)
        .extrude(band_width)
    )

    fillet_radius = band_width * 0.45 
    
    try:
        ring = ring.edges(">Z or <Z").edges(">R").fillet(fillet_radius)
    except:
        pass 

    return ring