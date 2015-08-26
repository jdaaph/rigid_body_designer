import itertools as it

GRID_SQUARE = 0
GRID_HEX_HORIZ = 1
GRID_HEX_VERT = 2

class SquareGrid(object):
  """ Implements a square grid, with functions implemented to manage
  all the specifics of how grid coordinates are laid out in the plane.
  This is so that it's easy to replace a
  square grid with a hex grid of some sort. """

  def __init__(self):
    """ Nothing to do here... """
    pass

  @property
  def grid_type(self):
    return GRID_SQUARE

  def points_iterator(self, box):
    """ Returns an iterator to all points within the box. """
    return it.product(range(box[0], box[2]), range(box[1], box[3]))

  def gridcoord_to_pixel(self, coord, cell_diameter):
    """ Converts the grid coordinate to a pixel coordinate.
    Assumes:
      - the origin grid coordinate (0,0) corresponds to pixel (0,0)
      - grid coordinates increase in the same directions as pixel coords (i.e. down and to the right)
      - each grid cell has width and height equal to cell_diameter
    """
    x = coord[0] * cell_diameter
    y = coord[1] * cell_diameter
    return (x, y)
  def pixel_to_gridcoord(self, pixel, cell_diameter):
    coord_x = int(pixel[0] / cell_diameter)
    coord_y = int(pixel[1] / cell_diameter)
    return (coord_x, coord_y)

  def calc_bbox(self, gridcoords, padding = 0):
    """ Returns the smallest bounding box in grid points containing all grid points given, with the given padding.
    If no points are given, None is returned. """

    if len(gridcoords) == 0:
      return None

    min_x = min([p[0] for p in gridcoords]) - padding
    min_y = min([p[1] for p in gridcoords]) - padding
    max_x = max([p[0] for p in gridcoords]) + padding + 1
    max_y = max([p[1] for p in gridcoords]) + padding + 1
    return (min_x, min_y, max_x, max_y)

  def gridcoord_to_pixel_bbox(self, gc_bbox, cell_diameter):
    """ Returns the smallest bounding box in pixels containing the given grid coordinate bounding box. """
    if gc_bbox == None:
      return None

    min_x, min_y, max_x, max_y = gc_bbox
    top_left = self.gridcoord_to_pixel((min_x, min_y), cell_diameter)
    bottom_right = self.gridcoord_to_pixel((max_x, max_y), cell_diameter)
    return (top_left[0], top_left[1], bottom_right[0], bottom_right[1])

  def pixel_to_gridcoord_bbox(self, pixel_bbox, cell_diameter):
    """ Returns the smallest bounding box in grid coordinates containing the given pixel bounding box. """
    if pixel_bbox == None:
      return None

    min_x, min_y, max_x, max_y = pixel_bbox
    top_left = self.pixel_to_gridcoord((min_x, min_y), cell_diameter)
    bottom_right = self.pixel_to_gridcoord((max_x-1, max_y-1), cell_diameter)
    return (top_left[0], top_left[1], bottom_right[0]+1, bottom_right[1]+1)

  def gridcoord_in_bbox(self, gridcoord, gc_bbox):
    if gc_bbox == None:  return False

    x, y = gridcoord
    min_x, min_y, max_x, max_y = gc_bbox
    return min_x <= x < max_x and min_y <= y < max_y