
import Tkinter as tk
import ttk
import itertools as it

from model import Model
import grid
import Operation
from brush import Brush
from copy import deepcopy

sticky_all = tk.N + tk.S + tk.E + tk.W

MOD_SHIFT = 0x1
MOD_CTRL = 0x4
MOD_BTN1 = 0x100
MOD_LEFTALT = 0x0008  

def box_contains_box(box1, box2):
  return (box1[0] <= box2[0] <= box1[2]
      and box1[0] <= box2[2] <= box1[2]
      and box1[1] <= box2[1] <= box1[3]
      and box1[1] <= box2[3] <= box1[3])
def box_union(box1, box2):
  return (min(box1[0], box2[0]), min(box1[1], box2[1]),
          max(box1[2], box2[2]), max(box1[3], box2[3]))

class ModelCanvas(tk.Canvas):
  """ ModelCanvas implements a subclass of Tkinter.Canvas that displays the points in a Model object
  based on the corresponding grid. The purpose of the ModelCanvas is to both display the Model object
  and to allow editing operations to modify the Model object in an intuitive fashion.
  The ModelCanvas implements the following functionality:
    - Stores a single Model object for which particles are displayed on the canvas
    - Allows selection of any number of grid coordinates
    - Tracks displayed particles that need updating, allowing updates to be delayed until an operation is complete
    - Stores a Brush object that determines how particles are modified when painted.
    - Emits a ModelChangedEvent when the underlying Model object has been modified [NOT IMPLEMENTED]
  The ModelCanvas queries the underlying Model object for information about
    - which grid coordinates are in the model
    - characteristics (particle/body types) of the corresponding particles
    - bounding boxes for the entire model with a given amount of padding
  The ModelCanvas queries the Model object's grid object for information about
    - conversion between grid coordinates and pixels on the canvas
    - bounding boxes for arbitrary collections of grid coordinates
    - lists of all grid coordinates within a given bounding box (including those without a corresponding particle) 
  """

  _model = None

  _oval_to_gridcoord = None
  _gridcoord_to_oval = None
  _drawn_bbox = None

  _diameter = 20.0 ## diameter of spheres, in unzoomed distance units (pixels?)
  _zoom = 1.0 ## Zoom level (1 = no zoom)
  _show_blank_particles = True

  _dirty = None

  _selection = None

  _brush = None

  # current_operation = None
  # left_press_coord records where the left mouse btn has been pressed, this would determine if an action is a click or drag
  # left_press_coord = None

  def __init__(self, master, show_blanks = True, **kargs):
    tk.Canvas.__init__(self, master, bd = 0, highlightthickness = 0, **kargs)


    ## Set up display functionality
    
    # Set up dicts that map between drawn ovals and grid coordinates
    self._oval_to_gridcoord = dict()
    self._gridcoord_to_oval = dict()

    # Set initial scroll region
    self['scrollregion'] = (0, 0, 0, 0)
    self._drawn_bbox = self.scrollable_bbox

    # Flags for drawing
    self._show_blank_particles = show_blanks

    # Initialize list of grid coordinates needing updating
    self._dirty = set([])


    ## Set up edit functionality

    # Initialize to empty selection
    self._selection = set([])

    # Initialize to erasing brush
    self._brush = None


    ## Add basic event handlers
    self.bind('<Configure>', self.handle_resize)
    self.bind_all('<<Brush>>', self.handle_brush_event)
    # self.bind('<Command-r>', self.handle_cmdr)
    # self.bind('<Command-v>', self.handle_cmdv)
    # self.bind('<Command-m>', self.handle_cmdm)
    # self.bind('<Command-c>', self.handle_cmdc)
    # self.bind('<Return>', self.handle_enter)
    # self.bind('<BackSpace>', self.handle_backspace)


  #### General canvas properties

  @property
  def model(self):
    return self._model
  @model.setter
  def model(self, model):
    self._model = model
    self._dirty = set(self.points_iterator())
    self.update()


  #### Model displaying properties
  
  ## General

  @property
  def zoom(self):
    return self._zoom
  @zoom.setter
  def zoom(self, zoom):
    self._zoom = zoom
    self._dirty = set(self.points_iterator())  

  @property
  def diameter(self):
    """ TODO: Make 'diameter' a property of Model or Particle objects """
    return self._diameter * self._zoom

  @property
  def show_blank_particles(self):
    return self._show_blank_particles
  @show_blank_particles.setter
  def show_blank_particles(self, show_blanks):
    self._show_blank_particles = show_blanks
    self._dirty |= set(self.points_iterator()) - set(self._model.points_iterator())

  ## Screen display info
  # Note: drawn >= scrollable >= model, visible
  @property
  def drawn_bbox(self):
    """ Returns the canvas region for which particles have been drawn. """
    return self._drawn_bbox
  @property
  def scrollable_bbox(self):
    """ Returns the bounding box covering the currently scrollable region of canvas. """
    return [float(v) for v in self['scrollregion'].split(' ')]
  @property
  def model_bbox(self):
    """ Returns the bounding box for the model + padding. """
    return self.model.grid.grid_coord_to_pixel_bbox(self.model.calc_bbox(), self.diameter)
  @property
  def visible_bbox(self):
    """ Returns the bounding box for the canvas's currently visible area. """
    topleft = (self.canvasx(0), self.canvasy(0))
    dims = (self.winfo_width(), self.winfo_height())
    return (topleft[0], topleft[1], topleft[0] + dims[0], topleft[1] + dims[1])


  #### Model editing properties

  @property
  def brush(self):
    return self._brush
  @brush.setter
  def brush(self, brush):
    self._brush = brush

  @property
  def selection(self):
    return frozenset(self._selection)
  @selection.setter
  def selection(self, selection):
    self._dirty |= self._selection ^ selection
    self._selection = selection


  #### Display functionality

  def update(self, update_all = False):
    """ Force updates for canvas components, including:
      - Checking for new particles to draw
      - Redrawing changed particles (if update_all is set, then redraw all particles)
      - Updating canvas scrolling region
    """
    ## Update scroll region to include viewable area and model
    self.update_scrollregion()

    ## Update particle information
    self.update_particles(update_all)

  def update_scrollregion(self):
    """ Resize the canvas scrollregion to make sure the entire model is viewable. """
    ## If there are any points in the model, make sure the scrollable region covers the entire model
    ## Add scrolling if screen is too small.
    visible_box = self.visible_bbox
    model_box = self.model_bbox
    if model_box != None:
      self['scrollregion'] = box_union(visible_box, model_box)
    else:
      self['scrollregion'] = visible_box

  def update_particles(self, update_all = False):
    """ Add new particles to canvas and update for any changes since last update. """
    ## Add new ovals to canvas, if necessary
    if update_all or not box_contains_box(self.drawn_bbox, self.scrollable_bbox):
      self._add_particles()

    ## Update locations/colors of particles on canvas
    if update_all:
      self._redraw_particles(self.points_iterator())
      self._dirty.clear()
    else:
      self._redraw_particles()


  #### Misc functionality

  def points_iterator(self):
    """ Returns an iterator over all points currently in the canvas/model's scrollable bounding box."""
    box = self.model.grid.pixel_to_grid_coord_bbox(self.scrollable_bbox, self.diameter)
    return self.model.grid.points_iterator(box)


  #### Private member functions. Don't mess with these unless you know what you're doing.

  def _add_particle(self, gridcoord):
    """ Add a single new oval to the canvas at the particular grid coordinate. """
    oval_id = self.create_oval(0, 0, 0, 0, tags = 'particle', state = tk.HIDDEN)

    self.tag_bind(oval_id, "<ButtonPress-1>", lambda e: self.handle_left_press(e))
    self.tag_bind(oval_id, "<ButtonRelease-1>", lambda e, c=gridcoord: self.handle_left_release(e, c))

    self.tag_bind(oval_id, "<Button-2>", lambda e,c=gridcoord: self.handle_right_click(e, c))
    self.tag_bind(oval_id, "<B2-Motion>", self.handle_right_drag)

    self._oval_to_gridcoord[oval_id] = gridcoord
    self._gridcoord_to_oval[gridcoord] = oval_id

  def _add_particles(self):
    """ Check that all grid coords in the scrollable region are drawn on the canvas,
    adding any new ones, if necessary. The drawn_bbox variable is updated. """
    for gridcoord in self.points_iterator():
      if gridcoord not in self._gridcoord_to_oval:
        self._add_particle(gridcoord)
        self._dirty.add(gridcoord)
    self._drawn_bbox = box_union(self.drawn_bbox, self.scrollable_bbox)

  def _redraw_particle(self, gridcoord):
    """ Updates the location/size of the single given particle on the canvas.
    TODO: This might be easier/more elegant if we used tags. """
    diameter = self.diameter
    canvas_x0, canvas_y0 = self.model.grid.grid_coord_to_pixel(gridcoord, diameter)
    canvas_x1 = canvas_x0 + diameter
    canvas_y1 = canvas_y0 + diameter

    oval_id = self._gridcoord_to_oval[gridcoord]
    self.coords(oval_id, canvas_x0, canvas_y0, canvas_x1, canvas_y1)
    
    in_model = self.model.has_particle(gridcoord)
    in_selection = gridcoord in self.selection
    hidden = not in_model and not self.show_blank_particles

    particle_specs = self.model.get_particle_type(gridcoord)
    body_specs = self.model.get_body_type(gridcoord)

    state = tk.HIDDEN if hidden else tk.NORMAL
    fill = particle_specs.color if in_model else '#CCC'
    outline = body_specs.color if in_model else '#999'
    width = 4 if in_selection else 2

    self.itemconfigure(oval_id, fill = fill, outline = outline, width = width, state = state)
    if in_selection:  self.tag_raise(oval_id, 'particle')
  
  def _redraw_particles(self, dirty = None):
    """ Update the locations/sizes of particles in the iterable dirty.
    Use _add_particles() to draw particles for the first time on the canvas. """
    if dirty == None:
      dirty = self._dirty
      self._dirty.clear()

    for gridcoord in dirty:
      self._redraw_particle(gridcoord)

  def _apply_brush(self, brush, gridcoords):
    """ Set the particles corresponding to the given grid coordinates to have
    the particle and/or body type specified by the brush. """
    erase = brush == None
    create = brush.particle_specs != None or brush.body_specs != None
    modify = not erase and not create
    for gridcoord in gridcoords:
      if erase:
        self.model.remove_particle(gridcoord)
      elif (create or modify) and self.model.has_particle(gridcoord):
        if brush.particle_specs != None:  self.model.set_particle_specs(gridcoord, brush.particle_specs)
        if brush.body_specs != None:  self.model.set_body_specs(gridcoord, brush.body_specs)
      elif create and not self.model.has_particle(gridcoord):
        self.model.add_particle(gridcoord, brush.particle_specs, brush.body_specs)

    ### Emit model-changed event
    self.event_generate('<<Model>>')


  #### Event handlers

  def handle_brush_event(self, event):
    print "*", dir(event)

  def handle_resize(self, event):
    self.update(update_all = True)

  def handle_right_drag(self, event):
    x = self.canvasx(event.x)
    y = self.canvasy(event.y)
    gridcoord = self.model.grid.pixel_to_grid_coord((x,y), self.diameter)
    self.handle_right_click(event, gridcoord)
  def handle_right_click(self, event, gridcoord):
    def normal_click():
      self.selection = set([gridcoord])
    def shift_click():
      if gridcoord in self._selection:
        return
      box = self.model.grid.calc_bbox(list(self._selection) + [gridcoord])
      self.selection = set(self.model.grid.points_iterator(box))
    def ctrl_click():
      if gridcoord in self._selection:
        self.selection = self._selection - set([gridcoord])
      else:
        self.selection = self._selection | set([gridcoord])
    def leftalt_click():
      body_coords = self.model.calc_connected_body_particles(gridcoord)
      self.selection = set(body_coords)

    if event.state & MOD_SHIFT:
      shift_click()
    elif event.state & MOD_CTRL:
      ctrl_click()
    elif event.state & MOD_LEFTALT:
      leftalt_click()
    else:
      normal_click()
    self._redraw_particles()

  # def handle_left_press(self, event):
  #   self.focus_set()
  #   x = self.canvasx(event.x)
  #   y = self.canvasy(event.y)
  #   print "Press: " + str((x,y))
  #   grid_coord = self.canvas_grid.pixel_to_grid_coord((x,y), self.cur_diameter())
  #   self.left_press_coord = grid_coord

  # def handle_left_release(self, event, particle):
  #   '''Determine if a left mouse event is click or drag, then call the right handle func'''
  #   self.focus_set()
  #   x = self.canvasx(event.x)
  #   y = self.canvasy(event.y)
  #   print "Release: " + str((x,y))
  #   new_coord = self.canvas_grid.pixel_to_grid_coord((x,y), self.cur_diameter())
  #   old_coord = self.left_press_coord
  #   if new_coord[0] == old_coord[0] and new_coord[1] == old_coord[1]:
  #     self.handle_left_click(event, particle)
  #   else:
  #     self.handle_left_drag(event, old_coord, new_coord)
  #   self.left_press_coord = None

  def handle_left_click(self, event, grid_coord):
    brush = self._brush
    selection = self._selection
    if gridcoord not in selection:
      self.selection = set([gridcoord])

    self._apply_brush(brush, selection)
    self.update()


  # def handle_left_drag(self, event, old_coord, new_coord):
  #   ''' left drag is move, with initial and final mouse position as base/ref point'''
  #   self.focus_set()
  #   bp = self.grid_coord_to_particle[old_coord] 
  #   rp = self.grid_coord_to_particle[new_coord]
  #   # perform a copy if command is held, perform a move by default
  #   if self.selected_particles:
  #     if event.state & MOD_LEFTALT:
  #       operation = Operation.Copy(model=self, cache={'selected':self.selected_particles, 'not_selected':self.not_selected()}, 
  #           operation_box=self.master.master.options_box.operation_box)
  #     else:
  #       operation = Operation.Move(model=self, cache={'selected':self.selected_particles, 'not_selected':self.not_selected()}, 
  #           operation_box=self.master.master.options_box.operation_box)

  #     self.current_operation = operation
  #     operation.fill_cache([bp])
  #     operation.paste([rp])

  # def generate_snapshot(self, width, height):
  #   diameter = self.cur_diameter()
  #   box = self.model.grid.grid_coord_to_pixel_bbox(self.model_bbox(), diameter)

  #   snapshot = tk.Canvas(None, highlightthickness = 0, bg = '#CCCCCC')
  #   if box == None:
  #     return snapshot

  #   min_x, min_y, max_x, max_y = [int(v) for v in box]

  #   print box
  #   scale = min(float(height) / (max_y - min_y), float(width) / (max_x - min_x))
  #   print width, height, scale

  #   for grid_coord in self.model.points_iterator():
  #     x0, y0 = self.model.grid.grid_coord_to_pixel(grid_coord, diameter)
  #     x0 -= min_x
  #     y0 -= min_y
  #     x1 = x0 + diameter
  #     y1 = y0 + diameter
  #     particle_color = self.model.get_particle_type(grid_coord).color
  #     body_color = self.model.get_body_type(grid_coord).color
  #     snapshot.create_oval(x0, y0, x1, y1, tags='all', fill = particle_color, outline = body_color, width = 1)
  #   snapshot.scale('all', 0, 0, scale, scale)
    
  #   return snapshot

  # new library begins
  # def calc_contiguous_body_coords(self, grid_coord):
  #   '''returns a list of particles in the same body as particle.
  #   TODO: Only return coordinates contiguous to the given coordinate'''
  #   body = self.model.get_body_type(grid_coord)
  #   buddies = []
  #   for ite in self.particles:
  #     if ite.body_specs == body and ite.present: 
  #       buddies.append(ite)
  #   return buddies

  # def not_selected(self):
  #   not_selected = []
  #   for par in self.particles:
  #     if par not in self.selected_particles:
  #       not_selected.append(par)
  #   return not_selected

  # def handle_cmdr(self, event):
  #   print "Pressed R"
  #   if self.selected_particles:

  #     self.current_operation = Operation.Rotate_ccw(model=self, cache={'selected':self.selected_particles, 'not_selected':self.not_selected()}, 
  #       operation_box=self.master.master.options_box.operation_box)  

  # def handle_cmdm(self, event):
  #   print "Pressed M"
  #   if self.selected_particles:
  #     self.current_operation = Operation.Move(model=self, cache={'selected':self.selected_particles, 'not_selected':self.not_selected()}, 
  #       operation_box=self.master.master.options_box.operation_box)
  # 
  # def handle_cmdc(self, event):
  #   print "Pressed C"
  #   if self.selected_particles:
  #     self.current_operation = Operation.Copy(model=self, cache={'selected':self.selected_particles, 'not_selected':self.not_selected()}, 
  #       operation_box=self.master.master.options_box.operation_box) 

  # def handle_cmdv(self, event):
  #   print "Pressed V"
  #   single_par_selected = len(self.selected_particles) == 1
  #   if single_par_selected and self.current_operation:
  #     self.current_operation.paste(self.selected_particles)

  # def handle_enter(self, event):
  #   print "Pressed Enter"
  #   single_par_selected = len(self.selected_particles) == 1
  #   if single_par_selected and self.current_operation:
  #     self.current_operation.fill_cache(self.selected_particles)

  # def handle_backspace(self, event):
  #   if self.selected_particles:
  #     selected = list(self.selected_particles)
  #     for par in selected:
  #       par.present = False
  #       self.model_particles.remove(par)
  #       par.particle_specs = self.default_brush.particle_specs
  #       par.body_specs = self.default_brush.body_specs

  #     self.redraw_particles(selected)
  #     self.selected_particles.clear()

###########
  # def set_particles_paste(self, particles, invisible_list):
  #   '''invisible_list solves the problem of some not present particles will also need to be copied'''
  #   # self.apply_brush(self.default_brush, self.model_particles)
  #   # for p in self.model_particles:  p.present = False
  #   for p in self.model_particles:  p.present = False

  #   dirty = []
  #   dirty.extend(self.model_particles)
  #   dirty.extend(self.selected_particles)

  #   self.model_particles.clear()
  #   self.selected_particles.clear()
  #   
  #   for new_p in particles:
  #     if new_p.grid_coord not in self.grid_coord_to_particle:
  #       self.add_new_particle(new_p.grid_coord)
  #     old_p = self.grid_coord_to_particle[new_p.grid_coord]
  #     old_p.particle_specs = new_p.particle_specs
  #     old_p.body_specs = new_p.body_specs
  #     # old_p.present = True
  #     # not to draw the non-present particles
  #     old_p.present = False
  #     # set present attribute correctly
  #     if new_p.grid_coord not in invisible_list:
  #       old_p.present = True
  #       self.model_particles.add(old_p)

  #  dirty.extend(self.model_particles)
  #  self.redraw_particles(dirty)
  #  self.update_grid_size()

