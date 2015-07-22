import Tkinter as tk
import ttk
import itertools as it

import advanced
from brush import Brush

sticky_all = tk.N + tk.S + tk.E + tk.W

GRID_SQUARE = 0
GRID_HEX_HORIZ = 1
GRID_HEX_VERT = 2

MOD_SHIFT = 0x1
MOD_CTRL = 0x4
MOD_BTN1 = 0x100
MOD_LEFTALT = 0x0008  

def box_contains_box(box1, box2):
  return (box1[0] < box2[0] < box1[2]
      and box1[0] < box2[2] < box1[2]
      and box1[1] < box2[1] < box1[3]
      and box1[1] < box2[3] < box1[3])
def box_union(box1, box2):
  return (min(box1[0], box2[0]), min(box1[1], box2[1]),
          max(box1[2], box2[2]), max(box1[3], box2[3]))

class Model(tk.Canvas):
  grid_type = GRID_SQUARE
  canvas_grid = None
  min_grid_padding = 10 ## minimum number of blank spheres to extend past model
  
  model_particles = None

  selected_particles = None

  oval_id_to_particle = None
  grid_coord_to_particle = None

  get_brush = None
  default_brush = None

  diameter = 20 ## diameter of spheres, in unzoomed distance units (pixels?)
  zoom = 1.0 ## Zoom level (1 = no zoom)

  current_operation = None

  def __init__(self, master, brush_func, default_brush = None, grid_type = GRID_SQUARE):
    tk.Canvas.__init__(self, master, bd = 0, highlightthickness = 0)

    ## Set grid_type variable
    self.grid_type = grid_type

    ## Initialize particles in model (to empty list)
    self.model_particles = set([])

    ## Initialize to empty selection
    self.selected_particles = set([])

    ## Draw spheres on canvas for the first time
    self.oval_id_to_particle = dict()
    self.grid_coord_to_particle = dict()
    self.current_operation = None

    ## Initialize to erasing brush
    self.get_brush = brush_func
    if default_brush == None:  self.default_brush = self.get_brush()
    else: self.default_brush = default_brush
    
    self.init_grid()

    ## Add resizing event handler
    self.bind('<Configure>', self.handle_resize)
    self.bind('<Command-r>', self.handle_cmdr)
    self.bind('<Command-v>', self.handle_cmdv)
    self.bind('<Command-c>', self.handle_cmdc)
    self.bind('<Return>', self.handle_enter)

  @property
  def particles(self):
    return list(self.model_particles)

  def set_particles(self, particles):
    self.apply_brush(self.default_brush, self.model_particles)
    for p in self.model_particles:  p.present = False

    dirty = []
    dirty.extend(self.model_particles)
    dirty.extend(self.selected_particles)

    self.model_particles.clear()
    self.selected_particles.clear()

    for new_p in particles:
      if new_p.grid_coord not in self.grid_coord_to_particle:
        self.add_new_particle(new_p.grid_coord)
      old_p = self.grid_coord_to_particle[new_p.grid_coord]
      old_p.particle_specs = new_p.particle_specs
      old_p.body_specs = new_p.body_specs
      old_p.present = True
      self.model_particles.add(old_p)

    dirty.extend(self.model_particles)
    self.redraw_particles(dirty)
    self.update_grid_size()

  def init_grid(self):
    """ Initializes the canvas to a minimum size. Draws the canvas """
    if self.grid_type == GRID_SQUARE:
      self.canvas_grid = SquareGrid(2 * self.min_grid_padding, 2 * self.min_grid_padding)
    else:
      assert False, "Grid type {0} not supported.".format(self.grid_type)

    self.update_grid_size()

  def update_grid_size(self):
    """ Resizes the canvas grid as necessary to have room for the exposed section of canvas and the model + padding.
    If changes were made to the grid, redraws new spheres. """
    ## Check if canvas grid covers entire screen, and increase canvas grid size if necessary.
    canvas_box = self.canvas_bounding_box()
    dirty = self.canvas_grid.cover_pixels(canvas_box, self.cur_diameter())

    ## If there are any points in the model, make sure the canvas grid and screen cover the entire model + padding
    ## Increase canvas grid size if canvas grid is too small. Add scrolling if screen is too small.
    model_points = [p.grid_coord for p in self.model_particles]
    model_box = self.canvas_grid.calc_pixel_bounding_box(model_points, self.cur_diameter(), self.min_grid_padding)
    if model_points != [] and not box_contains_box(canvas_box, model_box):
      dirty |= self.canvas_grid.cover_pixels(model_box, self.cur_diameter())
      old_box = [float(v) for v in self["scrollregion"].split(" ")]
      if not box_contains_box(old_box, model_box):
        self["scrollregion"] = box_union(model_box, canvas_box)
    else:
      self["scrollregion"] = (0, 0, 0, 0)

    ## Redraw points if changes were made (dirty = True)
    if dirty:
      self.draw_new_particles();

  def add_new_particle(self, grid_coord):
    oval_id = self.create_oval(0, 0, 0, 0, tags = 'particle', state = tk.HIDDEN)
    particle = Particle(grid_coord, oval_id, self.default_brush.particle_specs, self.default_brush.body_specs)

    self.tag_bind(oval_id, "<Button-1>", lambda e,p=particle: self.handle_left_click(e, p))
    self.tag_bind(oval_id, "<B1-Motion>", self.handle_left_drag)
    self.tag_bind(oval_id, "<Button-2>", lambda e,p=particle: self.handle_right_click(e, p))
    self.tag_bind(oval_id, "<B2-Motion>", self.handle_right_drag)

    self.oval_id_to_particle[oval_id] = particle
    self.grid_coord_to_particle[grid_coord] = particle

    return particle

  def draw_new_particles(self):
    """ Draw spheres on the canvas if they are not yet added, but don't update the locations of
    old spheres. """
    points = self.canvas_grid.points_iterator()
    for grid_coord in points:
      if grid_coord not in self.grid_coord_to_particle:
        particle = self.add_new_particle(grid_coord)
        self.redraw_particle(particle)

  def redraw_particle(self, particle):
    """ Updates the location/size of the single given particle on the canvas.
    TODO: This might be easier/more elegant if we used tags. """
    diameter = self.cur_diameter()
    canvas_x0, canvas_y0 = self.canvas_grid.grid_coord_to_pixel(particle.grid_coord, diameter)
    canvas_x1 = canvas_x0 + diameter
    canvas_y1 = canvas_y0 + diameter

    shape_id = particle.shape_id
    self.coords(shape_id, canvas_x0, canvas_y0, canvas_x1, canvas_y1)

    fill = particle.particle_specs.color if particle.present else '#CCC'
    outline = particle.body_specs.color if particle.present else '#999'
    width = 4 if particle in self.selected_particles else 2

    self.itemconfigure(shape_id, fill = fill, outline = outline, width = width, state = tk.NORMAL)
    if particle in self.selected_particles:  self.tag_raise(particle.shape_id, 'particle')
  
  def redraw_particles(self, dirty = None):
    """ Update the locations/sizes of particles in the iterable dirty.
    Use draw_new_spheres() to add new particles to the grid. """
    if dirty == None:
      dirty = self.grid_coord_to_particle.values()

    for particle in dirty:
      self.redraw_particle(particle)

  def redraw_brush_change(self):
    brush = self.get_brush()
    dirty = []
    for p in self.grid_coord_to_particle.values():
      if p.particle_specs == brush.particle_specs or p.body_specs == brush.body_specs:
        dirty.append(p)
    self.redraw_particles(dirty)


  def apply_brush(self, brush, particles):
    erase = brush.particle_specs == None and brush.body_specs == None
    for p in particles:
      if erase and p in self.model_particles:
        p.present = False
        self.model_particles.remove(p)
        p.particle_specs = self.default_brush.particle_specs
        p.body_specs = self.default_brush.body_specs
      elif not erase:
        p.present = True
        self.model_particles.add(p)
        if brush.particle_specs != None:  p.particle_specs = brush.particle_specs
        if brush.body_specs != None:  p.body_specs = brush.body_specs


  def canvas_bounding_box(self):
    topleft = (self.canvasx(0), self.canvasy(0))
    dims = (self.winfo_width(), self.winfo_height())
    return (topleft[0], topleft[1], topleft[0] + dims[0], topleft[1] + dims[1])

  def cur_diameter(self):
    return self.diameter * self.zoom

  def handle_resize(self, event):
    self.focus_set()
    self.update_grid_size()

  def handle_right_drag(self, event):
    self.focus_set()
    x = self.canvasx(event.x)
    y = self.canvasy(event.y)
    grid_coord = self.canvas_grid.pixel_to_grid_coord((x,y), self.cur_diameter())
    self.handle_right_click(event, self.grid_coord_to_particle[grid_coord])
  def handle_right_click(self, event, particle):
    def normal_click():
      dirty = list(self.selected_particles)
      dirty.append(particle)
      self.selected_particles = set([particle])
      return dirty
    def shift_click():
      if particle in self.selected_particles:
        return []
      self.selected_particles.add(particle)
      box = self.canvas_grid.calc_bounding_box([p.grid_coord for p in self.selected_particles])
      self.selected_particles = set([self.grid_coord_to_particle[c] for c in self.canvas_grid.points_iterator(box)])
    def ctrl_click():
      if particle in self.selected_particles:
        self.selected_particles.remove(particle)
      else:
        self.selected_particles.add(particle)
      return [particle]
    def leftalt_click():
      body = Model.buddy_finder(self,particle)
      for par in body:
        self.selected_particles.add(par)
      return body

    self.focus_set()
    if event.state & MOD_SHIFT:
      dirty = shift_click()
    elif event.state & MOD_CTRL:
      dirty = ctrl_click()
    elif event.state & MOD_LEFTALT:
      dirty = leftalt_click()
    else:
      dirty = normal_click()
    self.redraw_particles(dirty)

  def handle_left_drag(self, event):
    self.focus_set()
    x = self.canvasx(event.x)
    y = self.canvasy(event.y)
    grid_coord = self.canvas_grid.pixel_to_grid_coord((x,y), self.cur_diameter())
    self.handle_left_click(event, self.grid_coord_to_particle[grid_coord])
  def handle_left_click(self, event, particle):
    self.focus_set()
    brush = self.get_brush()
    dirty = list(self.selected_particles) # List of particles that need redrawing
    if particle not in self.selected_particles:
      dirty.append(particle)
      self.selected_particles = set([particle])

    self.apply_brush(brush, self.selected_particles)
    self.update_grid_size()
    self.redraw_particles(dirty)

  def generate_snapshot(self, width, height):
    diameter = self.cur_diameter()
    box = self.canvas_grid.calc_pixel_bounding_box([p.grid_coord for p in self.model_particles], diameter, self.min_grid_padding)

    snapshot = tk.Canvas(None, highlightthickness = 0, bg = '#CCCCCC')
    if box == None:
      return snapshot

    min_x, min_y, max_x, max_y = [int(v) for v in box]

    print box
    scale = min(float(height) / (max_y - min_y), float(width) / (max_x - min_x))
    print width, height, scale

    for particle in self.model_particles:
      x0, y0 = self.canvas_grid.grid_coord_to_pixel(particle.grid_coord, diameter)
      x0 -= min_x
      y0 -= min_y
      x1 = x0 + diameter
      y1 = y0 + diameter
      snapshot.create_oval(x0, y0, x1, y1, tags='all', fill = particle.particle_specs.color, outline = particle.body_specs.color, width = 1)
    snapshot.scale('all', 0, 0, scale, scale)
    
    return snapshot

  # new library begins
  def buddy_finder(self, particle):
    '''returns a list of particles in the same body as particle is'''
    body = particle.body_specs
    buddies = []
    for ite in self.particles:
      if ite.body_specs == body: 
        buddies.append(ite)
    return buddies

  def not_selected(self):
    not_selected = []
    for par in self.particles:
      if par not in self.selected_particles:
        not_selected.append(par)
    return not_selected

  def handle_cmdr(self, event):
    print "Pressed R"
    if self.selected_particles:
      self.current_operation = advanced.Rotate_ccw(model=self, cache={'group':self.selected_particles, 'not_selected':self.not_selected()})  

  def handle_cmdc(self, event):
    print "Pressed C"
    if self.selected_particles:
      self.current_operation = advanced.Copy(model=self, cache={'group':self.selected_particles})

  def handle_cmdv(self, event):
    print "Pressed V"
    single_par_selected = len(self.selected_particles) == 1
    if single_par_selected and self.current_operation:
      self.current_operation.paste(self.selected_particles)
      self.current_operation = None

  def handle_enter(self, event):
    print "Pressed Enter"
    single_par_selected = len(self.selected_particles) == 1
    if single_par_selected and self.current_operation:
      self.current_operation.fill_cache(self.selected_particles)
  
###########
  def set_particles_paste(self, particles):
    self.apply_brush(self.default_brush, self.model_particles)
    for p in self.model_particles:  p.present = False

    dirty = []
    dirty.extend(self.model_particles)
    dirty.extend(self.selected_particles)

    self.model_particles.clear()
    self.selected_particles.clear()

    for new_p in particles:
      if new_p.grid_coord not in self.grid_coord_to_particle:
        self.add_new_particle(new_p.grid_coord)
      old_p = self.grid_coord_to_particle[new_p.grid_coord]
      old_p.particle_specs = new_p.particle_specs
      old_p.body_specs = new_p.body_specs
      old_p.present = True
      self.model_particles.add(old_p)

    dirty.extend(self.model_particles)
    self.redraw_particles(dirty)
    self.update_grid_size()


class SquareGrid(object):
  """ Implements a square grid, with functions implemented so that
  the DesignCanvas doesn't have to worry about any specifics about how
  the grid takes up space. This is more so that it's easy to replace a
  square grid with a hex grid of some sort. """
  min_x = 0
  min_y = 0
  width = 0
  height = 0

  def __init__(self, width, height):
    """ Creates a grid approximately centered around the origin. """
    self.min_x = -width / 2
    self.min_y = -height / 2
    self.width = width
    self.height = height

  def get_width(self):
    return self.width
  def get_height(self):
    return self.height
  def get_max_x(self):
    return self.min_x + self.width - 1
  def get_max_y(self):
    return self.min_y + self.height - 1

  def set_width(self, width):
    """ Sets the grid width to the given width. The width change is
    distributed approximately evenly across the left and right of the grid. """
    width_change = width - self.get_width()
    self.min_x -= width_change / 2
    self.width = width
  def set_height(self, height):
    """ Sets the grid height to the given height. The height change is
    distributed approximately evenly across the top and bottom of the grid. """
    height_change = height - self.get_height()
    self.min_y -= height_change / 2
    self.height = height

  def points_iterator(self, box = None):
    """ Returns an iterator to all points within the box.
    If box == None, then the iterator iterates over all points in the grid. """
    if box != None:
      return it.product(range(box[0], box[2] + 1), range(box[1], box[3] + 1))
    else:
      return it.product(range(self.min_x, self.min_x + self.width), range(self.min_y, self.min_y + self.height))

  def calc_bounding_box(self, points, padding = 0):
    """ Returns the smallest bounding box in grid points containing all grid points given, with the given padding.
    If no points are given, None is returned. """
    if len(points) == 0:
      return None
    min_x = min([p[0] for p in points]) - padding
    min_y = min([p[1] for p in points]) - padding
    max_x = max([p[0] for p in points]) + padding
    max_y = max([p[1] for p in points]) + padding
    return (min_x, min_y, max_x, max_y)
  def calc_pixel_bounding_box(self, points, cell_diameter, padding = 0):
    """ Returns the smallest bounding box in pixels containing all grid points given, with the given padding.
    If no points are given, None is returned. """
    if len(points) == 0:
      return None
    min_x, min_y, max_x, max_y = self.calc_bounding_box(points, padding)
    top_left = self.grid_coord_to_pixel((min_x, min_y), cell_diameter)
    bottom_right = self.grid_coord_to_pixel((max_x, max_y), cell_diameter)
    return (top_left[0], top_left[1], bottom_right[0] + cell_diameter, bottom_right[1] + cell_diameter)

  def grid_coord_to_pixel(self, coord, cell_diameter):
    """ Converts the grid coordinate to a pixel coordinate.
    Assumes:
      - the origin grid coordinate (0,0) corresponds to pixel (0,0)
      - grid coordinates increase in the same directions as pixel coords (i.e. down and to the right)
      - each grid cell has width and height equal to cell_diameter
    """
    x = coord[0] * cell_diameter
    y = coord[1] * cell_diameter
    return (x, y)
  def pixel_to_grid_coord(self, pixel, cell_diameter):
    coord_x = int(pixel[0] / cell_diameter)
    coord_y = int(pixel[1] / cell_diameter)
    return (coord_x, coord_y)

  def covers_pixels(self, pixel_bounding_box, cell_diameter):
    box = self.covered_pixels(cell_diameter)
    return box_contains_box(box, pixel_bounding_box)

  def cover_pixels(self, pixel_bounding_box, cell_diameter):
    """ Ensure that the grid size will cover the given pixel_bounding_box.
    cell_diameter gives the width and height of each grid cell.
    Increases the width/height if necessary, but never decreases the grid size. """
    if self.covers_pixels(pixel_bounding_box, cell_diameter):  return False

    min_x, min_y = self.pixel_to_grid_coord((pixel_bounding_box[0], pixel_bounding_box[1]), cell_diameter)
    max_x, max_y = self.pixel_to_grid_coord((pixel_bounding_box[2], pixel_bounding_box[3]), cell_diameter)
    min_width = max_x - min_x + 3
    min_height = max_y - min_y + 3

    if min_x < self.min_x:  self.min_x = min_x
    if min_y < self.min_y:  self.min_y = min_y
    if self.get_max_x() < max_x:  self.width = max_x - self.min_x + 1
    if self.get_max_y() < max_y:  self.height = max_y - self.min_y + 1

    return True

  def covered_pixels(self, cell_diameter):
    """ Returns the (width, height) in pixels of area covered by the grid. """
    pix_min_x, pix_min_y = self.grid_coord_to_pixel((self.min_x, self.min_y), cell_diameter)
    pix_max_x, pix_max_y = self.grid_coord_to_pixel((self.get_max_x(), self.get_max_y()), cell_diameter)
    return (pix_min_x, pix_min_y, pix_max_x, pix_max_y)



class Particle(object):
  grid_coord = None
  shape_id = None

  present = False
  particle_specs = None
  body_specs = None
  def __init__(self, grid_coord, shape_id, particle_specs, body_specs):
    self.grid_coord = grid_coord
    self.shape_id = shape_id

    self.particle_specs = particle_specs
    self.body_specs = body_specs