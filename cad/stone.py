import cadquery as cq

def add_stone(ring, size):
    radius = size / 2.0
    stone_height = size * 0.8  
    
    embed_depth = 1.0 
    
    bbox = ring.val().BoundingBox()
    outer_radius = bbox.xmax 
    z_center = (bbox.zmax + bbox.zmin) / 2.0 
    
    stone = (
        cq.Workplane("YZ")
        .workplane(offset=outer_radius + stone_height - embed_depth) 
        .center(0, z_center)                           
        .circle(radius)                                
        .extrude(-stone_height, taper=30)              
    )
    
    return ring.union(stone)