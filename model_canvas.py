
import Tkinter as tk
import ttk
import itertools as it

from model import Model
from model_canvas_operation import MCO_Move
from particle import DrawnParticle
import grid
import utils
import Operation
from brush import Brush
from copy import deepcopy
from model_canvas_layer import ViewLayer, EditBackgroundLayer

sticky_all = tk.N + tk.S + tk.E + tk.W

MOD_SHIFT = 0x1
MOD_CTRL = 0x4
MOD_BTN1 = 0x100
MOD_LEFTALT = 0x0008  


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
    self._gridcoord_to_particle = dict()

    self._diameter = 20.0 ## diameter of spheres, in unzoomed distance units (pixels?)
    self._zoom = 1.0 ## Zoom level (1 = no zoom)
    self._padding = 10 ## Padding to surround model with, in units of cell diameter
    self._show_nonmodel_particles = False

    # Set initial scroll region
    self['scrollregion'] = (0, 0, 0, 0)

    # Initialize list of grid coordinates needing updating
    self._dirty = set([])

    ## Add basic event handlers
    self.bind('<Configure>', self.handle_resize)
    self.bind_all('<<Model>>', self.handle_model_event, add='+')


  #### General canvas properties

  @property
  def model(self):
    return self._model
  @model.setter
  def model(self, model):
    self._add_new_gridcoords(model.points_iterator())
    new_model_particles = set([self._gridcoord_to_particle[gc] for gc in model.points_iterator()])
    dirty_particles = set(self.particles_iterator()) | new_model_particles

    self._model = model
    self.mark_dirty(dirty_particles)
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
  def show_nonmodel_particles(self):
    return self._show_nonmodel_particles
  @show_nonmodel_particles.setter
  def show_nonmodel_particles(self, show_blanks):
    self._show_nonmodel_particles = show_blanks
    self.mark_dirty(self.nonmodel_particles_iterator())

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
    """ Request updates for canvas components, including:
      - Checking for new particles to draw
      - Redrawing changed particles (if update_all is set, then redraw all particles)
      - Updating canvas scrolling region
    """
    ## Only run this when we're idle, to prevent long updates from slowing down the system (too much)
    self.after_idle(self._force_update, update_all)

  def update_scrollregion(self):
    """ Resize the canvas scrollregion to make sure the entire model is viewable. """
    ## If there are any points in the model, make sure the scrollable region covers the entire model
    ## Add scrolling if screen is too small.
    visible_box = self.visible_bbox
    model_box = self.model_bbox
    self['scrollregion'] = utils.box_union(visible_box, model_box)
    self._add_new_gridcoords()

  def update_particles(self, update_all = False):
    """ Add new particles to canvas and update for any changes since last update. """
    ## Update locations/colors of particles on canvas
    if update_all:
      self._draw_particles(self.particles_iterator())
      self.mark_clean()
    else:
      self._draw_particles()


  def get_dirty(self):
    """ Returns an iterable of the drawn particles marked as needing to be redrawn,
    due to changes in particle/body type, etc. """
    return self._dirty

  def mark_dirty(self, particles = None):
    """ Marks the given iterable of DrawnParticles as dirty (needing redrawing).
    If particles is omitted, then all drawn particles are marked dirty. """
    if particles == None:
      self._dirty = set(self.particles_iterator())
    else:
      assert all([p != None for p in particles])
      self._dirty |= set(particles)

  def mark_clean(self, particles = None):
    """ Marks the given gridcoords as clean (not needing redrawing).
    If gridcoords is omitted, then all particles are considered clean. """
    if particles == None:
      self._dirty = set([])
    else:
      self._dirty -= set(particles)


  #### Particle information

  def points_iterator(self):
    """ Returns an iterator over all points currently in the canvas/model's scrollable bounding box."""
    if self.model == None:
      return iter([])
    else:
      box = self.model.grid.pixel_to_grid_coord_bbox(self.scrollable_bbox, self.diameter)
      return self.model.grid.points_iterator(box)
  def particles_iterator(self):
    """ Returns an iterator over all particles drawn on the canvas, including those not corresponding
    to a particle in the model. """
    return iter(self._gridcoord_to_particle.values())
  def model_particles_iterator(self):
    """ Returns an iterator over all particles drawn on the canvas, including those not corresponding
    to a particle in the model. """
    return filter(lambda p: p.in_model, self.particles_iterator())
  def nonmodel_particles_iterator(self):
    """ Returns an iterator over all particles drawn on the canvas, including those not corresponding
    to a particle in the model. """
    return filter(lambda p: not p.in_model, self.particles_iterator())


  def particle_in_model(self, p):
    return p.in_model
  def particle_hidden(self, p):
    return not p.in_model and not self.show_nonmodel_particles
  def point_in_model(self, gridcoord):
    return self.model.has_particle(gridcoord)
  def point_hidden(self, gridcoord):
    return not self.point_in_model(gridcoord) and not self.show_nonmodel_particles
  def point_drawn(self, gridcoord):
    return gridcoord in self._gridcoord_to_particle

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
    if zoom == 1:
      return

    self.zoom *= zoom
    new_x1 = model_x1*zoom - (vis_w - model_w*zoom) / 2.0
    new_y1 = model_y1*zoom - (vis_h - model_h*zoom) / 2.0
    new_x2 = model_x2*zoom + (vis_w - model_w*zoom) / 2.0
    new_y2 = model_y2*zoom + (vis_h - model_h*zoom) / 2.0
    self['scrollregion'] = (new_x1, new_y1, new_x2, new_y2)
    self._add_new_gridcoords()


  #### Private member functions. Don't mess with these unless you know what you're doing.

  def _add_gridcoord(self, gridcoord):
    """ Add a single new oval to the canvas at the particular grid coordinate. """
    oval_id = self.create_oval(0, 0, 0, 0, tags = 'particle', state = tk.HIDDEN)

    model_p = self.model.get_particle(gridcoord)
    p = DrawnParticle(gridcoord = gridcoord, oval_id = oval_id, model_particle = model_p)
    self._gridcoord_to_particle[gridcoord] = p
    return p
  def _add_new_gridcoords(self, gridcoords = None):
    """ Checks the list of grid coordinates, adding any that have not yet been drawn.
    If gridcoords is omitted, all grid coordinates in the scrollable region are checked.
    Slow, so don't call unless you need to. """
    if gridcoords == None: gridcoords = self._find_new_gridcoords()
    particles = []
    for gridcoord in gridcoords:
      if not self.point_drawn(gridcoord) and not self.point_hidden(gridcoord):
        particles.append(self._add_gridcoord(gridcoord))
    self.mark_dirty(particles)
    if len(particles) > 0:  print 'added', len(particles), 'new particles'
  def _find_new_gridcoords(self):
    """ Returns a list of all grid coordinates that are in the scrollable region
    but not yet added to the canvas. """
    gridcoords = []
    for gridcoord in self.points_iterator():
      if not self.point_drawn(gridcoord):
        gridcoords.append(gridcoord)
    return gridcoords

  def _get_oval_coords(self, p):
    """ Returns the coordinates of the oval as a tuple. Set the oval coordinates with
    self.coords(oval_id, *coords) """
    ## Calculate shape location
    diameter = self.diameter
    canvas_x0, canvas_y0 = self.model.grid.grid_coord_to_pixel(p.gridcoord, diameter)
    canvas_x1 = canvas_x0 + diameter
    canvas_y1 = canvas_y0 + diameter
    return (canvas_x0, canvas_y0, canvas_x1, canvas_y1)
  def _get_oval_characteristics(self, p):
    """ Returns the drawing parameters of the oval as a dict.
    Redraw the oval characteristics with self.itemconfigure(oval_id, **characteristics). """
    fill = p.particle_specs.color if p.in_model else '#CCC'
    outline = p.body_specs.color if p.in_model else '#999'
    width = 2
    state = tk.HIDDEN if self.particle_hidden(p) else tk.NORMAL
    return dict(fill = fill, outline = outline, width = 2, state = state)

  def _draw_shown_particle(self, p):
    """ Update a particle if it is not being hidden. """
    ## Get the shape id
    oval_id = p.oval_id
    self.coords(oval_id, *self._get_oval_coords(p))
    self.itemconfigure(oval_id, **self._get_oval_characteristics(p))
  def _draw_hidden_particle(self, p):
    """ Update a particle if it is hidden. """
    oval_id = p.oval_id
    if self.itemconfigure(oval_id, 'state') != tk.HIDDEN:
      self.itemconfigure(oval_id, state = tk.HIDDEN)

  def _draw_particle(self, p):
    """ Updates the location/size of the single given particle on the canvas.
    TODO: This might be easier/more elegant if we used tags. """
    ## Display particle based on whether it's hidden or not.
    p.model_particle = self.model.get_particle(p.gridcoord)
    if self.particle_hidden(p):
      self._draw_hidden_particle(p)
    else:
      self._draw_shown_particle(p)
  
  def _draw_particles(self, dirty = None):
    """ Update the locations/sizes of particles in the iterable dirty.
    If particles have not been added yet, they are drawn for the first time on the canvas. """
    if dirty == None:
      dirty = self.get_dirty()
      self.mark_clean()

    for p in dirty:
      self._draw_particle(p)
    if len(dirty) > 0:  print 'drew', len(dirty), 'particles'

  def _force_update(self, update_all):
    ## Update scroll region to include viewable area and model
    self.update_scrollregion()

    ## Update particle information
    self.update_particles(update_all)


  #### Event handlers

  def handle_resize(self, event):
    self.update()

  def handle_model_event(self, event):
    event_data = utils.event_data_retrieve(event.state)
    if self.model != event_data['model']:  return

    dirty_gridcoords = event_data['dirty_gridcoords']
    self._add_new_gridcoords(dirty_gridcoords)
    dirty_particles = [self._gridcoord_to_particle[gc] for gc in dirty_gridcoords if self.point_drawn(gc)]

    self.mark_dirty(dirty_particles)
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

  def __init__(self, master, **kargs):
    ModelView.__init__(self, master, **kargs)

    # Flags for drawing
    self._show_nonmodel_particles = True

    ## Set up edit functionality

    # Initialize to empty selection, copy list, cut list
    self._selected = set([]) # Currently selected particles
    self._copied = set([]) # Particles copied to clipboard
    self._cut = set([]) # Particles being manipulated

    # Initialize to erasing brush
    self._brush = None

    # Initialize to normal editing mode
    self._mode = self.MODE_NORMAL

    # Initialize operation information dict (stores data for current operation)
    self.cur_operation = None

    ## Add basic event handlers
    # Link virtual events to key-presses (conceivably, we could use different keypresses for Mac/Windows)
    self.event_add('<<MoveDrag>>', '<B1-Motion>')
    self.event_add('<<Undo>>', '<Command-z>')
    self.event_add('<<Copy>>', '<Command-c>')
    self.event_add('<<Cut>>', '<Command-x>')
    self.event_add('<<Paste>>', '<Command-v>')
    self.event_add('<<Rotate>>', '<Command-r>')
    self.event_add('<<Flip>>', '<Command-f>')

    self.bind('<ButtonPress-1>', self.handle_leftpress)
    self.bind('<ButtonRelease-1>', self.handle_leftrelease)
    self.bind('<ButtonPress-2>', self.handle_rightpress)

    self.bind('<<Paint>>', self.handle_paint)
    self.bind('<<MoveDrag>>', self.handle_movedrag)
    self.bind('<<MoveEnd>>', self.handle_moveend)
    self.bind_all('<<Undo>>', self.handle_undo)
    self.bind_all('<<Copy>>', self.handle_copy)
    self.bind_all('<<Cut>>', self.handle_cut)
    self.bind_all('<<Paste>>', self.handle_paste)
    self.bind_all('<<Rotate>>', self.handle_rotate)
    self.bind_all('<<Flip>>', self.handle_flip)

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
  def selected(self):
    return self._selected
  @selected.setter
  def selected(self, selected):
    self.mark_dirty(self._selected ^ selected)
    self._selected = selected

  @property
  def cut(self):
    return self._cut

  @property
  def copied(self):
    return self._copied

  # Editing modes (normal = paint/select, manipulate = with overlaid particles)
  def normal_mode(self):
    return self._mode == self.MODE_NORMAL
  def manipulate_mode(self):
    return self._mode == self.MODE_MANIPULATE
  def enter_manipulate_mode(self):
    self._cut = self.selected
    self._mode = self.MODE_MANIPULATE
  def exit_mainpulate_mode(self):
    self._mode = self.MODE_NORMAL

  #### Model editing functions
  def apply_brush(self, brush, particles):
    """ Set the given particles to have the particle and/or body type specified by the brush.
    Does NOT redraw particles to reflect the changes! Use update() to do this. """
    erase = brush == None
    modify = not erase and (brush.particle_specs == None or brush.body_specs == None)
    create = not erase and not modify
    print erase, modify, create
    for p in particles:
      if erase:
        self.model.remove_particle(p.gridcoord)
      elif (create or modify) and p.in_model:
        if brush.particle_specs != None:  p.particle_specs = brush.particle_specs
        if brush.body_specs != None:  p.body_specs = brush.body_specs
      elif create and not p.in_model:
        self.model.add_particle(p.gridcoord, brush.particle_specs, brush.body_specs)
    self.mark_dirty(particles)
    
    ### Emit model-changed event
    gridcoords = [p.gridcoord for p in particles]
    key = utils.event_data_register(dict(dirty_gridcoords = gridcoords, model = self.model))
    self.event_generate('<<Model>>', state=key, when='tail')

  def apply_current_operation(self):
    changes = self.cur_operation.submit()

    dirty_gridcoords = [p.gridcoord for p in changes]
    for p in changes:
      print p.gridcoord, p.model_particle
      self._set_particle_at_gridcoord(p.gridcoord, p)

    self.cur_operation = None

    print 'particles changed:',len(changes)

    if self.normal_mode():
      key = utils.event_data_register(dict(model = self.model, dirty_gridcoords = dirty_gridcoords))
      self.event_generate('<<Model>>', state = key, when = 'tail')


  #### Particle information

  def particle_in_operation(self, p):
    return self.cur_operation != None and self.cur_operation.particle_in_operation(p)
  def particle_selected(self, p):
    return p in self._selected
  def point_selected(self, gridcoord):
    return self.point_drawn(gridcoord) and self.particle_selected(self._gridcoord_to_particle[gridcoord])

  #### Private member functions. Don't mess with these unless you know what you're doing.

  def _get_particle_at_gridcoord(self, gridcoord):
    if self.normal_mode():
      return self._gridcoord_to_particle[gridcoord]
    else:
      cut_dict = {p.gridcoord: p for p in self.cut}
      return cut_dict[gridcoord]
  def _set_particle_at_gridcoord(self, gridcoord, particle):
    old = self._get_particle_at_gridcoord(gridcoord)
    
    if self.normal_mode():
      if particle.in_model:
        self.model.set_particle(gridcoord, particle.model_particle)
      else:
        self.model.remove_particle(gridcoord)
      #print gridcoord, self.itemcget(particle.oval_id, 'fill')
    else:
      old.model_particle = particle.model_particle

    self.mark_dirty([old])

  def _get_oval_characteristics(self, particle):
    """ Returns characteristics of the oval corresponding to the given drawn particle.
    Extends ModelView._get_oval_characteristics to give selected particles a thicker border.
    Note that this modifies the behavior of ModelView._draw_particle(), which calls this function
    to determine the drawing parameters of the oval. """
    chars = ModelView._get_oval_characteristics(self, particle)
    if self.particle_selected(particle):
      chars['width'] = 4
    return chars

  def _add_gridcoord(self, gridcoord):
    """ Add a single new oval to the canvas at the particular drawn particle.
    Extends _add_particle in ModelView. """
    particle = ModelView._add_gridcoord(self, gridcoord)
    
    oval_id = particle.oval_id
    #self.tag_bind(oval_id, "<ButtonPress-1><ButtonRelease-1>", lambda e, p=particle: self.handle_left_click(e, p))
    #self.tag_bind(oval_id, "<ButtonRelease-1>", lambda e, c=gridcoord: self.handle_left_release(e, c))
    #self.tag_bind(oval_id, "<Button-2>", lambda e,p=particle: self.handle_right_click(e, p))
    #self.tag_bind(oval_id, "<B2-Motion>", self.handle_right_drag)
    return particle

  def _draw_operation_particle(self, p):
    """ Update a particle whose drawing characteristics are being handled by the 
    current operation. """
    #print 'operation handles drawing of particle @', p.gridcoord
    oval_id = p.oval_id
    self.coords(oval_id, *self.cur_operation.get_oval_coords(p))
    self.itemconfigure(oval_id, **self.cur_operation.get_oval_characteristics(p))

  def _draw_particle(self, p):
    """ Updates the location/size of the single given particle on the canvas.
    Replaces ModelView._draw_particle()
    TODO: This might be easier/more elegant if we used tags. """
    ## If the particle is controlled by the current operation, let the operation
    ## choose how to display it.
    ## Otherwise, display it based on whether it's hidden or not.
    if self.particle_in_operation(p):
      self._draw_operation_particle(p)
    else:
      ModelView._draw_particle(self, p)

    if self.particle_selected(p):
      oval_id = p.oval_id
      self.tag_raise(oval_id, 'particle')


  #### Event handlers

  def handle_brush_event(self, event):
    self.brush = utils.event_data_retrieve(event.state)

  def handle_paint(self, event):
    gridcoord = self.model.grid.pixel_to_grid_coord((event.x, event.y), self.diameter)
    particle = self._get_particle_at_gridcoord(gridcoord)
    brush = self._brush
    if not self.particle_selected(particle):
      self.selected = set([particle])

    self.apply_brush(brush, self._selected)
    self.update()

  def handle_movedrag(self, event):
    print 'movedrag'
    if self.cur_operation == None:
      startpos = (event.x, event.y)
      if self.normal_mode():
        particles = self.selected
      else:
        particles = self.cut
      self.cur_operation = MCO_Move(self, particles, startpos = startpos)

    self.cur_operation.set_duplicating(event.state & MOD_SHIFT)
    self.cur_operation.drag((event.x, event.y))
    self.update()

  def handle_moveend(self, event):
    print 'moveend'
    self.cur_operation.set_duplicating(event.state & MOD_SHIFT)
    self.apply_current_operation()
    self.update()

  def handle_undo(self, event):
    print 'undo'

  def handle_cut(self, event):
    print 'cut'

  def handle_copy(self, event):
    print 'copy'

  def handle_paste(self, event):
    print 'paste'

  def handle_rotate(self, event):
    print 'rotate'

  def handle_flip(self, event):
    print 'flip'

  def handle_leftpress(self, event):
    gridcoord = self.model.grid.pixel_to_grid_coord((event.x, event.y), self.diameter)
    particle = self._get_particle_at_gridcoord(gridcoord)
    if not self.particle_selected(particle):
      self.selected = set([particle])

  def handle_leftrelease(self, event):
    if self.cur_operation == None:
      self.event_generate('<<Paint>>', x = event.x, y = event.y)
    else:
      self.event_generate('<<MoveEnd>>', x = event.x, y = event.y)

  def handle_right_drag(self, event):
    x = self.canvasx(event.x)
    y = self.canvasy(event.y)
    gridcoord = self.model.grid.pixel_to_grid_coord((x,y), self.diameter)
    p = self._gridcoord_to_particle[gridcoord]
    self.handle_right_click(event, p)
  def handle_rightpress(self, event):
    def normal(particle):
      self.selected = set([particle])
    def shift(particle):
      if self.particle_selected(particle):
        return
      box = self.model.grid.calc_bbox([p.gridcoord for p in self._selected] + [particle.gridcoord])
      self.selected = set([self._gridcoord_to_particle[gc] for gc in self.model.grid.points_iterator(box)])
    def ctrl(particle):
      if self.particle_selected(particle):
        self.selected = self._selected - set([particle])
      else:
        self.selected = self._selected | set([particle])
    def leftalt(particle):
      body_coords = self.model.calc_connected_body_particles(particle.gridcoord)
      self.selected = set([self._gridcoord_to_particle[gc] for gc in body_coords])

    gridcoord = self.model.grid.pixel_to_grid_coord((event.x, event.y), self.diameter)
    particle = self._get_particle_at_gridcoord(gridcoord)
    if event.state & MOD_SHIFT:
      shift(particle)
    elif event.state & MOD_CTRL:
      ctrl(particle)
    elif event.state & MOD_LEFTALT:
      leftalt(particle)
    else:
      normal(particle)
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
class TestCanvas(tk.Canvas, object):
  def __init__(self, master, model = None, mode = 'view', **kargs):
    tk.Canvas.__init__(self, master, bd = 0, highlightthickness = 0, **kargs)

    self._model = model

    self._layers = []

    if mode == 'edit':
      self._layers.append(EditBackgroundLayer(self))
    elif mode == 'view':
      self._layers.append(ViewLayer(self))
    else:
      assert False, 'Unsupported mode: {0}'.format(mode)
    self.top_layer().start()

  @property
  def model(self):
    return self._model
  
  def set_model(self, model):
    self.background_layer().set_model(model)

  def top_layer(self):
    return self._layers[-1]
  def background_layer(self):
    return self._layers[0]
  def push_layer(self, layer):
    self._layers.append(layer)
  def pop_layer(self):
    return self._layers.pop()

  def start_layer(self, layer):
    self.top_layer().pause()
    self.push_layer(layer)
    self.top_layer().start()
  def merge_top_layer(self):
    layer = self.pop_layer()
    layer.finish()
    self.top_layer().merge(layer)
    layer.clean()
    self.top_layer().resume()
  def cancel_top_layer(self):
    layer = self._layers.pop()
    layer.cancel()
    layer.clean()
    self.top_layer().resume()

  def update_layer(self, layer):
    self.after_idle(layer.update)
    #print 'update requested:', layer



