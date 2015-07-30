
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

class ModelView(tk.Canvas, object):
  """ ModelView implements a Canvas subclass for solely displaying the points of a Model object.
  Editing is performed by the ModelEditor, which inherits from ModelView.
  The ModelView implements the following functionality:
    - Stores a single Model object for which particles are displayed on the canvas
    - Tracks displayed particles that need updating, allowing updates to be delayed until an operation is complete
  The ModelCanvas queries the underlying Model object for information about
    - which grid coordinates are in the model
    - characteristics (particle/body types) of the corresponding particles
    - bounding boxes for the entire model with a given amount of padding
  The ModelCanvas queries the Model object's grid object for information about
    - conversion between grid coordinates and pixels on the canvas
    - bounding boxes for arbitrary collections of grid coordinates
    - lists of all grid coordinates within a given bounding box (including those without a corresponding particle).
  """
  def __init__(self, master, **kargs):
    tk.Canvas.__init__(self, master, bd = 0, highlightthickness = 0, **kargs)

    self._model = None

    ## Set up display functionality
    
    # Set up dicts that map between drawn ovals and grid coordinates
    self._oval_to_gridcoord = dict()
    self._gridcoord_to_oval = dict()

    self._diameter = 20.0 ## diameter of spheres, in unzoomed distance units (pixels?)
    self._zoom = 1.0 ## Zoom level (1 = no zoom)
    self._padding = 10 ## Padding to surround model with, in units of cell diameter
    self._show_blank_particles = False

    # Set initial scroll region
    self['scrollregion'] = (0, 0, 0, 0)

    # Initialize list of grid coordinates needing updating
    self._dirty = set([])

    # Initialize set of particles in model
    self._model_coords = set([])

    ## Add basic event handlers
    self.bind('<Configure>', self.handle_resize)
    self.bind_all('<<Model>>', self.handle_model_event, add='+')


  #### General canvas properties

  @property
  def model(self):
    return self._model
  @model.setter
  def model(self, model):
    self._model = model
    self._model_coords = set(model.points_iterator())
    self.mark_dirty()
    self.update()


  #### Model displaying properties
  
  ## General

  @property
  def zoom(self):
    return self._zoom
  @zoom.setter
  def zoom(self, zoom):
    self.mark_dirty()
    self._zoom = zoom
    self.update_scrollregion()
    self.mark_dirty()

  @property
  def diameter(self):
    """ TODO: Make 'diameter' a property of Model or Particle objects """
    return self._diameter * self._zoom

  @property
  def padding(self):
    """ Padding to surround the model with, in grid units. """
    return self._padding
  @padding.setter
  def padding(self, p):
    self._padding = p
    self.update_scrollregion()

  @property
  def show_blank_particles(self):
    return self._show_blank_particles
  @show_blank_particles.setter
  def show_blank_particles(self, show_blanks):
    self._show_blank_particles = show_blanks
    self.mark_dirty(set(self.points_iterator()) - set(self._model.points_iterator()))

  ## Screen display info
  # Note: scrollable >= model, visible
  @property
  def scrollable_bbox(self):
    """ Returns the bounding box covering the currently scrollable region of canvas. """
    return [float(v) for v in self['scrollregion'].split(' ')]
  @property
  def model_bbox(self):
    """ Returns the bounding box for the model + padding. """
    if self.model == None or len(self.model.particles) == 0:
      return None
    box = self.model.grid.grid_coord_to_pixel_bbox(self.model.calc_bbox(), self.diameter)
    pix_padding = self.padding * self.diameter
    x1,y1,x2,y2 = box
    return (x1 - pix_padding, y1 - pix_padding, x2 + pix_padding, y2 + pix_padding)
  @property
  def visible_bbox(self):
    """ Returns the bounding box for the canvas's currently visible area. """
    topleft = (self.canvasx(0), self.canvasy(0))
    dims = (self.winfo_width(), self.winfo_height())
    return (topleft[0], topleft[1], topleft[0] + dims[0], topleft[1] + dims[1])


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
    self.mark_dirty(set(self.points_iterator()) - set(self._gridcoord_to_oval.keys()))


  def update_particles(self, update_all = False):
    """ Add new particles to canvas and update for any changes since last update. """
    ## Update locations/colors of particles on canvas
    if update_all:
      self._draw_particles(self.points_iterator())
      self.mark_clean()
    else:
      self._draw_particles()

  def get_dirty(self):
    """ Returns an iterable of the grid coordinates marked as needing to be redrawn,
    due to changes in particle/body type, etc. """
    return self._dirty

  def mark_dirty(self, gridcoords = None):
    """ Marks the given iterable of gridcoords as dirty (needing redrawing).
    If gridcoords is omitted, then all particles are marked dirty. """
    if gridcoords == None:
      self._dirty = set(self.points_iterator())
    else:
      self._dirty |= set(gridcoords)

  def mark_clean(self, gridcoords = None):
    """ Marks the given gridcoords as clean (not needing redrawing).
    If gridcoords is omitted, then all particles are considered clean. """
    if gridcoords == None:
      self._dirty = set([])
    else:
      self._dirty -= set(gridcoords)

  #### Particle information

  def points_iterator(self):
    """ Returns an iterator over all points currently in the canvas/model's scrollable bounding box."""
    if self.model == None:
      return iter([])
    else:
      box = self.model.grid.pixel_to_grid_coord_bbox(self.scrollable_bbox, self.diameter)
      return self.model.grid.points_iterator(box)

  def point_in_model(self, gridcoord):
    return self.model.has_particle(gridcoord)
  def point_hidden(self, gridcoord):
    return not self.point_in_model(gridcoord) and not self.show_blank_particles
  def point_drawn(self, gridcoord):
    return gridcoord in self._gridcoord_to_oval

  #### Misc functionality

  def show_entire_model(self):
    """ Sets the zoom level and canvas viewing position to center the entire model
    in the viewing area. """
    model_box = self.model_bbox
    vis_box = self.visible_bbox
    if model_box == None:
      return

    model_x1, model_y1, model_x2, model_y2 = model_box
    vis_x1, vis_y1, vis_x2, vis_y2 = vis_box
    model_w = model_x2 - model_x1
    model_h = model_y2 - model_y1
    vis_w = vis_x2 - vis_x1
    vis_h = vis_y2 - vis_y1
    zoom = min(float(vis_w) / model_w, float(vis_h) / model_h)

    self.zoom *= zoom
    new_x1 = model_x1*zoom - (vis_w - model_w*zoom) / 2.0
    new_y1 = model_y1*zoom - (vis_h - model_h*zoom) / 2.0
    new_x2 = model_x2*zoom + (vis_w - model_w*zoom) / 2.0
    new_y2 = model_y2*zoom + (vis_h - model_h*zoom) / 2.0
    self['scrollregion'] = (new_x1, new_y1, new_x2, new_y2)
    self.mark_dirty(set(self.points_iterator()) - set(self._gridcoord_to_oval.keys()))


  #### Private member functions. Don't mess with these unless you know what you're doing.

  def _add_particle(self, gridcoord):
    """ Add a single new oval to the canvas at the particular grid coordinate. """
    oval_id = self.create_oval(0, 0, 0, 0, tags = 'particle', state = tk.HIDDEN)

    self._oval_to_gridcoord[oval_id] = gridcoord
    self._gridcoord_to_oval[gridcoord] = oval_id

  def _get_oval_coords(self, gridcoord):
    """ Returns the coordinates of the oval as a tuple. Set the oval coordinates with
    self.coords(oval_id, *coords) """
    ## Calculate shape location
    diameter = self.diameter
    canvas_x0, canvas_y0 = self.model.grid.grid_coord_to_pixel(gridcoord, diameter)
    canvas_x1 = canvas_x0 + diameter
    canvas_y1 = canvas_y0 + diameter
    return (canvas_x0, canvas_y0, canvas_x1, canvas_y1)
  def _get_oval_characteristics(self, gridcoord):
    """ Returns the drawing parameters of the oval as a dict.
    Redraw the oval characteristics with self.itemconfigure(oval_id, **characteristics). """
    particle_specs = self.model.get_particle_type(gridcoord)
    body_specs = self.model.get_body_type(gridcoord)
    fill = particle_specs.color if self.point_in_model(gridcoord) else '#CCC'
    outline = body_specs.color if self.point_in_model(gridcoord) else '#999'
    width = 2
    state = tk.HIDDEN if self.point_hidden(gridcoord) else tk.NORMAL
    return dict(fill = fill, outline = outline, width = 2, state = state)

  def _draw_shown_particle(self, gridcoord):
    """ Update a particle if it is in the model. """
    if not self.point_drawn(gridcoord):
      self._add_particle(gridcoord)
    ## Get the shape id
    oval_id = self._gridcoord_to_oval[gridcoord]
    self.coords(oval_id, *self._get_oval_coords(gridcoord))
    self.itemconfigure(oval_id, **self._get_oval_characteristics(gridcoord))
  def _draw_hidden_particle(self, gridcoord):
    """ Update a particle if it is hidden.
    Hidden particles are not added to save time.
    If an already-added particle is hidden, then we set its state to tk.HIDDEN to hide it.
    """
    if self.point_drawn(gridcoord):
      oval_id = self._gridcoord_to_oval[gridcoord]
      self.itemconfigure(oval_id, state = tk.HIDDEN)

  def _draw_particle(self, gridcoord):
    """ Updates the location/size of the single given particle on the canvas.
    TODO: This might be easier/more elegant if we used tags. """
    ## If it's hidden, draw it only if it's already added
    if self.point_hidden(gridcoord):
      self._draw_hidden_particle(gridcoord)
    else:
      self._draw_shown_particle(gridcoord)
  
  def _draw_particles(self, dirty = None):
    """ Update the locations/sizes of particles in the iterable dirty.
    If particles have not been added yet, they are drawn for the first time on the canvas. """
    if dirty == None:
      dirty = self.get_dirty()
      self.mark_clean()

    for gridcoord in dirty:
      self._draw_particle(gridcoord)


  #### Event handlers

  def handle_resize(self, event):
    self.update()

  def handle_model_event(self, event):
    new_coords = set(self.model.points_iterator())
    self.mark_dirty(new_coords | self._model_coords)
    self._model_coords = new_coords
    self.update()



class ModelCanvas(ModelView):
  """ ModelCanvas implements a subclass of Tkinter.Canvas that displays the points in a Model object
  based on the corresponding grid. The purpose of the ModelCanvas is to both display the Model object
  and to allow editing operations to modify the Model object in an intuitive fashion.
  In addition to the functionality of ModelView, the ModelCanvas implements the following functionality:
    - Stores a Brush object that determines how particles are modified when painted.
    - Generates a <<Model>> event when the underlying Model object has been modified
  This makes use of 'private' members of ModelView.... which is bad.
  """

  # current_operation = None
  # left_press_coord records where the left mouse btn has been pressed, this would determine if an action is a click or drag
  # left_press_coord = None

  MODE_NORMAL = 0
  MODE_MANIPULATE = 1

  def __init__(self, master, brush_func, **kargs):
    ModelView.__init__(self, master, **kargs)

    # Flags for drawing
    self._show_blank_particles = True

    ## Set up edit functionality

    # Initialize to empty selection
    self._selection = set([])

    # Initialize to erasing brush
    self._brush = None
    self._brush_func = brush_func

    # Initialize to normal editing mode
    self._mode = self.MODE_NORMAL

    ## Add basic event handlers
    # Link virtual events to key-presses (conceivably, we could use different keypresses for Mac/Windows)
    self.event_add('<<Drag>>', '<B1-Motion>')
    self.event_add('<<Move>>', '<B1-Motion><ButtonRelease-1>')
    self.event_add('<<MoveDuplicate>>', '<B1-Motion><Shift-ButtonRelease-1>')
    self.event_add('<<Undo>>', '<Command-z>')
    self.event_add('<<Copy>>', '<Command-c>')
    self.event_add('<<Cut>>', '<Command-x>')
    self.event_add('<<Paste>>', '<Command-v>')
    self.event_add('<<Rotate>>', '<Command-r>')
    self.event_add('<<Flip>>', '<Command-f>')
    def p(x): print x
    self.bind('<<Drag>>', lambda e: p('drag'))
    self.bind('<<Move>>', lambda e: p('move'))
    self.bind('<<MoveDuplicate>>', lambda e: p('movedup'))
    self.bind_all('<<Undo>>', lambda e: p('undo'))
    self.bind_all('<<Copy>>', lambda e: p('copy'))
    self.bind_all('<<Cut>>', lambda e: p('cut'))
    self.bind_all('<<Paste>>', lambda e: p('paste'))
    self.bind_all('<<Rotate>>', lambda e: p('rotate'))
    self.bind_all('<<Flip>>', lambda e: p('flip'))

    self.bind_all('<<Brush>>', self.handle_brush_event)
    # self.bind('<Command-r>', self.handle_cmdr)
    # self.bind('<Command-v>', self.handle_cmdv)
    # self.bind('<Command-m>', self.handle_cmdm)
    # self.bind('<Command-c>', self.handle_cmdc)
    # self.bind('<Return>', self.handle_enter)
    # self.bind('<BackSpace>', self.handle_backspace)


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
    self.mark_dirty(self._selection ^ selection)
    self._selection = selection

  @property
  def mode(self):
    return self._mode
  @mode.setter
  def mode(self, m):
    if m == self.MODE_NORMAL or m == self.MODE_MANIPULATE:
      self._mode = m
  def normal_mode(self):
    return self._mode == self.MODE_NORMAL
  def manipulate_mode(self):
    return self._mode == self.MODE_MANIPULATE

  #### Model editing functions
  def apply_brush(self, brush, gridcoords):
    """ Set the particles corresponding to the given grid coordinates to have
    the particle and/or body type specified by the brush.
    Does NOT make updates to reflect the changes! Use update() to do this. """
    erase = brush == None
    modify = not erase and (brush.particle_specs == None or brush.body_specs == None)
    create = not erase and not modify
    print erase, modify, create
    for gridcoord in gridcoords:
      if erase:
        self.model.remove_particle(gridcoord)
      elif (create or modify) and self.model.has_particle(gridcoord):
        if brush.particle_specs != None:  self.model.set_particle_type(gridcoord, brush.particle_specs)
        if brush.body_specs != None:  self.model.set_body_type(gridcoord, brush.body_specs)
      elif create and not self.model.has_particle(gridcoord):
        self.model.add_particle(gridcoord, brush.particle_specs, brush.body_specs)
    self.mark_dirty(gridcoords)
    
    ### Emit model-changed event
    self.event_generate('<<Model>>')

  #### Particle information

  def point_selected(self, gridcoord):
    return gridcoord in self._selection

  #### Private member functions. Don't mess with these unless you know what you're doing.

  def _get_oval_characteristics(self, gridcoord):
    """ Returns characteristics of the oval corresponding to the given grid coordinate.
    Extends ModelView._get_oval_characteristics to give selected particles a thicker border.
    Note that this modifies the behavior of ModelView._draw_particle(), which calls this function
    to determine the drawing parameters of the oval. """
    chars = ModelView._get_oval_characteristics(self, gridcoord)
    if self.point_selected(gridcoord):
      chars['width'] = 4
    return chars

  def _add_particle(self, gridcoord):
    """ Add a single new oval to the canvas at the particular grid coordinate.
    Extends _add_particle in ModelView. """
    ModelView._add_particle(self, gridcoord)
    
    oval_id = self._gridcoord_to_oval[gridcoord]
    self.tag_bind(oval_id, "<ButtonPress-1>", lambda e, c=gridcoord: self.handle_left_click(e, c))
    #self.tag_bind(oval_id, "<ButtonRelease-1>", lambda e, c=gridcoord: self.handle_left_release(e, c))
    self.tag_bind(oval_id, "<Button-2>", lambda e,c=gridcoord: self.handle_right_click(e, c))
    self.tag_bind(oval_id, "<B2-Motion>", self.handle_right_drag)

  def _draw_particle(self, gridcoord):
    """ Updates the location/size of the single given particle on the canvas.
    Extends ModelView._redraw_particle()
    TODO: This might be easier/more elegant if we used tags. """
    ModelView._draw_particle(self, gridcoord)
    if self.point_selected(gridcoord):
      oval_id = self._gridcoord_to_oval[gridcoord]
      self.tag_raise(oval_id, 'particle')


  #### Event handlers

  def handle_brush_event(self, event):
    self.brush = self._brush_func()

  def handle_right_drag(self, event):
    x = self.canvasx(event.x)
    y = self.canvasy(event.y)
    gridcoord = self.model.grid.pixel_to_grid_coord((x,y), self.diameter)
    self.handle_right_click(event, gridcoord)
  def handle_right_click(self, event, gridcoord):
    def normal_click():
      self.selection = set([gridcoord])
    def shift_click():
      if self.point_selected(gridcoord):
        return
      box = self.model.grid.calc_bbox(list(self._selection) + [gridcoord])
      self.selection = set(self.model.grid.points_iterator(box))
    def ctrl_click():
      if self.point_selected(gridcoord):
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
    self._draw_particles()

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

  def handle_left_click(self, event, gridcoord):
    brush = self._brush
    if not self.point_selected(gridcoord):
      self.selection = set([gridcoord])

    self.apply_brush(brush, self._selection)
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

