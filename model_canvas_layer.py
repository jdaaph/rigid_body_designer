import Tkinter as tk

import itertools

import utils
from model import Model
from particle import DrawnParticle

MOD_SHIFT = 0x1
MOD_MACCTRL = 0x4 # Mac 'control' key
MOD_CTRL = 0x8 # ctrl key (Mac 'command' key)
MOD_ALT = 0x10 # alt key (I think? TODO: verify this on multiple comps)
MOD_BTN1 = 0x100 # unverified

""" The Layer model for handling viewing and editing on a ModelCanvas
provides a modular and flexible framework for performing a variety of functions
and operations on a set of particles. Each Layer represents an operation or
step of an operation on a set of particles, and Layer objects may create other
layers in order to perform their function.
A Layer object is guaranteed to contain the following attributes:
  canvas
    The containing ModelCanvas object upon which particles are drawn and
    from which mouse events are captured.
  model
    A Model representation of the layer's non-blank particles
  start()
    Begins an operation.
    For simple operations, this may involve completing the entire action,
    such as rotating the particles. More complex operations may only
    display the particles and await further user input.
  pause(), resume()
    Merges the particles in the given layer into this one.
    Temporarily pauses and resumes an operation.
    This is used when one layer needs to create another layer to perform 
    some intermediate action. It mainly involves unbinding/rebinding event handlers
    so the next layer has full control over capturing user input.
  merge(layer)
    Merges the particles in the given layer into this one.
  merge_coordinates()
    Returns an iterable of coordinates in this layer that should be merged into the parent
    layer when merge() is called on the parent. Should only be called after finish() or
    cancel() has been executed.
  finish()
    Perform any final actions to complete the operation.
    The results are reflected in the underlying Model object.
  cancel()
    If any temporary changes were made, this is used to undo them.
    Functionally, this represents halting an operation midway, so no
    lasting changes should be made by a canceled operation.
  clean()
    Delete any displayed particles and clean up any data structures.
    A Layer should not be manipulated after calling clean().
  update()
    Perform drawing operations on the canvas to reflect any changes made during
    the operation.
The lifetime of a typical Layer object is usually something like:
  start() -> [pause() -> merge() -> resume()] -> finish()/cancel() -> clean()
with numerous calls to update() in the middle. When a Layer wishes to be updated,
it should call canvas.update_layer(self) to request an update at the next idle time.

Most Layers implement additional functionality on top of this, such as allowing
particles to be selected and implementing smart update strategies for drawing particles.
"""
### Layer Hierarchy
###  * ModelCanvasLayer: mostly dummy functionality
###      implements pausable event handlers
###        add_event_handler(), pause_event_handlers(), resume_event_handlers()
###        event handler lists: self.alive_event_handlers, self.running_event_handlers
###      implements status queries: started, paused, finished, canceled, alive, running
###  * ViewLayer(ModelCanvasLayer): basic viewing functionality of points in a model
###      displays particles in a particular model
###        self.model, set_model()
###      model viewing parameters:
###        diameter: diameter of drawnparticles
###        zoom: overall scaling of model
###        padding: padding (in units of diameter) around model
###      basic bounding box calculations
###        model_bbox(), visible_bbox()
###      viewing modes: self.viewmode = 
###        'auto' (model zoomfit and centered)
###        'scroll' (scrollregion always set to union of visible_bbox and model_bbox)
###        'none' (no automatic changes to view)
###      separate update functions for updating view and particles
###        update(), update_view(), update_particles()
###      gridcoord-based particle actions
###        add_particle_at(), get_particle_at(), set_particle_at(), add_particles_at()
###      dirty updating model for efficiently updating displayed particles
###        get_dirty(), mark_dirty(), mark_clean()
###      gridcoord/particle iterators
###        points_iterator()
###        particles_iterator(), model_particles_iterator(), nonmodel_particles_iterator()
###      gridcoord/particle flags/info
###        point_in_model(), point_hidden(), point_drawn()
###        particle_in_model(), particle_hidden()
###        particle_coords(), particle_params()
###      event handlers:
###        handle_resize(), handle_model_event() [alive]
###  * SelectLayer(ViewLayer)
###      selections of particles
###        self.selected
###      selection modification utilities
###        new_selection(), box_selection(), body_selection(), toggle_selection()
###      displaying selection
###        update_particle() [EXTENDS ViewLayer.update_particle()]
###      particle info
###        particle_selected(), point_selected()
###        particle_params() [EXTENDS ViewLayer.particle_params()]
###      selection controls: [self.running_event_handlers]
###        Left/RightClick = replace selection with clicked
###        Shift-RightClick = expand box selection to contain clicked
###        Command-RightClick = contiguous body selection
###        Shift-Command-RC = append contiguous body selection
###        handle_leftpress(), handle_rightpress()
###  * EditBasicLayer(SelectLayer)
###      event handlers for starting operations
###      paint selection
###      event handlers: [running]
###  * EditBackgroundLayer(EditBasicLayer)
###      draw nonmodel particles
###  * MoveLayer(SelectLayer)
###  * RotateLayer(SelectLayer)
###  * FlipLayer(SelectLayer)

class ModelCanvasLayer(object):

  
  def __init__(self, canvas, model):
    self._canvas = canvas
    self._model = model

    self._started = False
    self._paused = False
    self._finished = False
    self._canceled = False
    self._cleaned = False

    self.alive_event_handlers = [] # list of event handlers to have after starting
    self.running_event_handlers = [] # list of event handlers to have while current (i.e. top layer)

  @property
  def canvas(self):
    return self._canvas
  @property
  def model(self):
    return self._model

  @property
  def started(self):
    return self._started
  @property
  def paused(self):
    return self._paused
  @property
  def finished(self):
    return self._finished
  @property
  def canceled(self):
    return self._canceled
  @property
  def cleaned(self):
    return self._cleaned
  @property
  def alive(self):
    return self._started and not self._finished and not self._canceled
  @property
  def running(self):
    return self.alive and not self._paused


  def start(self):
    self.start_event_handlers(self.alive_event_handlers)
    self.start_event_handlers(self.running_event_handlers)
    self._started = True

  def pause(self):
    self.stop_event_handlers(self.running_event_handlers)
    self._paused = True
  def resume(self):
    self.start_event_handlers(self.running_event_handlers)
    self._paused = False
  def merge(self, layer):
    pass  
  def merge_coordinates(self):
    return []

  def finish(self):
    self.stop_event_handlers(self.alive_event_handlers)
    self.stop_event_handlers(self.running_event_handlers)
    self._finished = True
  def cancel(self):
    self.stop_event_handlers(self.alive_event_handlers)
    self.stop_event_handlers(self.running_event_handlers)
    self._canceled = True

  def clean(self):
    self._cleaned = True

  def update(self):
    pass

  ### We need event handlers that we can pause when a layer becomes inactive (not top layer)
  ### or is no longer alive.
  ### These functions add events to a given list that can be used to pause and resume
  ### event listening during runtime
  def start_event_handler(self, event, handler, tag):
    if tag == None:
      return self.canvas.bind(event, handler, add = '+')
    else:
      return self.canvas.bind_class(tag, event, handler, add = '+')
  def add_event_handler(self, handler_list, event, handler, tag = None):
    # TODO -- maybe have an EventInfo class instead of a list?
    handler_list.append([event, handler, tag, None])
  def stop_event_handlers(self, handler_list):
    for event_info in handler_list:
      ## event_info is list [event, handler, tag, funcid]
      event, handler, tag, funcid = event_info
      self.canvas.unbind(event, funcid)
      event_info[3] = None
  def start_event_handlers(self, handler_list):
    for event_info in handler_list:
      event, handler, tag, funcid = event_info
      assert funcid == None, 'Cannot resume event handlers.... not paused! {0}'.format(event_info)
      funcid = self.start_event_handler(event, handler, tag)
      event_info[3] = funcid

class ViewLayer(ModelCanvasLayer):
  """ The ViewLayer subclass implements a basic layer for displaying the particles
  in a Model object without implementing any editing functionality.
  Note that the pause(), resume(), finish(), and cancel() functions do nothing
  here as no user input is captured and no operation performed. merge() throws an error if it is called. """

  def __init__(self, canvas, model = None, viewmode = 'auto'):
    ModelCanvasLayer.__init__(self, canvas, model)

    # Set up dict to map between drawn particles and grid coordinates
    self._gridcoord_to_particle = dict()

    self._diameter = 20.0 ## diameter of spheres, in unzoomed distance units (pixels?)
    self._zoom = 1.0 ## Zoom level (1 = no zoom)
    self._padding = 10 ## Padding to surround model with, in units of cell diameter

    self._dirty = set([])

    self.viewmode = viewmode

    self.canvas['scrollregion'] = (0, 0, 0, 0)
    
    self.add_event_handler(self.alive_event_handlers, '<Configure>', self.handle_resize)
    self.add_event_handler(self.alive_event_handlers, '<<Model>>', self.handle_model_event, 'all')

  #### General properties

  @property
  def model(self):
    return self._model
  def set_model(self, model):
    self._model = model
    if self.started and model != None:
      self.add_particles_at(self.points_iterator())
      new_particles = set([self.get_particle_at(gc) for gc in self.points_iterator()])
      dirty_particles = set(self.particles_iterator()) | new_particles

      self.mark_dirty(dirty_particles)
      self.canvas.update_layer(self)


  @property
  def zoom(self):
    return self._zoom
  @zoom.setter
  def zoom(self, zoom):
    if self._zoom == zoom:  return
    self._zoom = zoom
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
    self.update_view()

  ## Screen display info
  # Note: scrollable >= model, visible
  @property
  def scrollable_bbox(self):
    """ Returns the bounding box covering the currently scrollable region of canvas. """
    return [float(v) for v in self.canvas['scrollregion'].split(' ')]
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
    topleft = (self.canvas.canvasx(0), self.canvas.canvasy(0))
    dims = (self.canvas.winfo_width(), self.canvas.winfo_height())
    return (topleft[0], topleft[1], topleft[0] + dims[0], topleft[1] + dims[1])

  #### Layer functionality
  def start(self):
    ModelCanvasLayer.start(self)

    self.add_particles_at(self.points_iterator())
    particles = set([self.get_particle_at(gc) for gc in self.points_iterator()])

    self.mark_dirty(particles)
    self.canvas.update_layer(self)

  def merge(self, layer):
    assert False, "Editing is not permitted with ViewBaseLayer"
  def merge_coordinates(self):
    return [p.gridcoord for p in self.particles_iterator() if not self.particle_hidden(p)]

  # pause/resume/finish/cancel are not overwritten from ModelCanvasLayer

  def pause(self):
    ModelCanvasLayer.pause(self)
    self.mark_dirty(self.particles_iterator())
    self.canvas.update_layer(self)

  def resume(self):
    ModelCanvasLayer.resume(self)
    self.mark_dirty(self.particles_iterator())
    self.canvas.update_layer(self)

  def clean(self):
    ModelCanvasLayer.clean(self)
    for p in self.particles_iterator():
      self.canvas.delete(p.oval_id)


  #### Display functionality

  def update(self):
    """ Update the zoom level and viewing box so the entire model is visible, and
    updates particles as needed. """
    self.update_view()
    self.update_particles()

  def update_view(self):
    if self.viewmode == 'auto':
      self.update_view_auto()
    elif self.viewmode == 'scroll':
      self.update_view_scroll()
    elif self.viewmode == 'none':
      pass
    else:
      assert False, 'Unrecognized view mode {0}'.format(self.viewmode)
  def update_view_auto(self):
    """ Zoom out so the entire model is viewable at once, and center the model in the screen. """
    ## If there are any points in the model, make sure the scrollable region covers the entire model
    ## Add scrolling if screen is too small.
    zoom = self._calc_zoomfit()
    offset = self._calc_centering_offset(zoom)
    vis_box = self.visible_bbox
    vis_w = vis_box[2] - vis_box[0]
    vis_h = vis_box[3] - vis_box[1]

    self.zoom *= zoom
    self.canvas['scrollregion'] = (offset[0], offset[1], offset[0] + vis_w, offset[1] + vis_h)
  def update_view_scroll(self):
    """ Resize the canvas scrollregion to make sure the entire model is viewable. """
    ## If there are any points in the model, make sure the scrollable region covers the entire model
    ## Add scrolling if screen is too small.
    visible_box = self.visible_bbox
    model_box = self.model_bbox
    self.canvas['scrollregion'] = utils.box_union(visible_box, model_box)


  def update_particles(self):
    """ Add new particles to canvas and update for any changes since last update. """
    ## Update locations/colors of particles on canvas
    for p in self.get_dirty():
      self.update_particle(p)
    #if len(self.get_dirty()) > 0:  print 'updated', len(self.get_dirty()), 'particles'
    self.mark_clean()

  def update_particle(self, p):
    p.model_particle = self.model.get_particle(p.gridcoord)
    coords = self.particle_coords(p)
    params = self.particle_params(p)
    if self.canvas.coords(p.oval_id) != coords:
      self.canvas.coords(p.oval_id, *coords)
    if any([self.canvas.itemcget(p.oval_id, key) != params[key] for key in params]):
      self.canvas.itemconfigure(p.oval_id, **params)

  def add_particle_at(self, gridcoord):
    """ Add a single new oval to the canvas at the particular grid coordinate. """
    oval_id = self.canvas.create_oval(0, 0, 0, 0, tags = ('particle', repr(self)), state = tk.HIDDEN)

    model_p = self.model.get_particle(gridcoord)
    p = DrawnParticle(gridcoord = gridcoord, oval_id = oval_id, model_particle = model_p)
    self._gridcoord_to_particle[gridcoord] = p
    return p
  def get_particle_at(self, gridcoord):
    return self._gridcoord_to_particle[gridcoord]
  def set_particle_at(self, gridcoord, p):
    old = self.get_particle_at(gridcoord)
    old.model_particle = p.model_particle
    if old.model_particle == None:
      self.model.remove_particle(gridcoord)
    else:
      self.model.set_particle(gridcoord, old.model_particle)
    self.mark_dirty([old])
  def add_particles_at(self, gridcoords):
    """ Checks the list of grid coordinates, adding any that have not yet been drawn.
    If gridcoords is omitted, all grid coordinates in the scrollable region are checked.
    Slow, so don't call unless you need to. """
    particles = []
    for gridcoord in gridcoords:
      if not self.point_drawn(gridcoord) and not self.point_hidden(gridcoord):
        particles.append(self.add_particle_at(gridcoord))
    self.mark_dirty(particles)
    if len(particles) > 0:  print 'added', len(particles), 'new particles'


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
      #assert all([p != None for p in particles])
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
    """ Returns an iterator over all points in the model."""
    if self.model == None:
      return iter([])
    else:
      return self.model.points_iterator()
  def particles_iterator(self):
    """ Returns an iterator over all particles being drawn in this layer.
    In this particular Layer, only model particles are drawn, but blank particles
    may remain when layers are switched in or out. """
    return self._gridcoord_to_particle.itervalues()
  def model_particles_iterator(self):
    """ Returns an iterator over all particles drawn on the canvas, including those not corresponding
    to a particle in the model. """
    return filter(lambda p: self.particle_in_model(p), self.particles_iterator())
  def nonmodel_particles_iterator(self):
    """ Returns an iterator over all particles drawn on the canvas, including those not corresponding
    to a particle in the model. """
    return filter(lambda p: not self.particle_in_model(p), self.particles_iterator())


  def particle_in_model(self, p):
    return p.in_model
  def particle_hidden(self, p):
    return not self.particle_in_model(p)
  def point_in_model(self, gridcoord):
    return self.model.has_particle(gridcoord)
  def point_hidden(self, gridcoord):
    return not self.point_in_model(gridcoord)
  def point_drawn(self, gridcoord):
    return gridcoord in self._gridcoord_to_particle

  def particle_coords(self, p):
    """ Returns the coordinates of the drawn particle as a tuple. Set the oval coordinates with
    coords(oval_id, *coords) """
    ## Calculate shape location
    diameter = self.diameter
    canvas_x0, canvas_y0 = self.model.grid.grid_coord_to_pixel(p.gridcoord, diameter)
    canvas_x1 = canvas_x0 + diameter
    canvas_y1 = canvas_y0 + diameter
    return (canvas_x0, canvas_y0, canvas_x1, canvas_y1)
  def particle_params(self, p):
    """ Returns the drawing parameters of the oval as a dict.
    Redraw the oval characteristics with self.itemconfigure(oval_id, **characteristics). """
    fill = p.particle_specs.color if p.in_model else '#CCC'
    outline = p.body_specs.color if p.in_model else '#999'
    if not self.running:
      fill = utils.color_blend(fill, '#FFF', .5)
      outline = utils.color_blend(outline, '#FFF', .5)
    width = 2
    state = tk.HIDDEN if self.particle_hidden(p) else tk.NORMAL
    return dict(fill = fill, outline = outline, width = 2, state = state)


  #### Misc functionality

  def _calc_zoomfit(self):
    model_box = self.model_bbox
    vis_box = self.visible_bbox
    if model_box == None:
      return 1

    model_x1, model_y1, model_x2, model_y2 = model_box
    vis_x1, vis_y1, vis_x2, vis_y2 = vis_box
    model_w = model_x2 - model_x1
    model_h = model_y2 - model_y1
    vis_w = vis_x2 - vis_x1
    vis_h = vis_y2 - vis_y1
    zoom = min(float(vis_w) / model_w, float(vis_h) / model_h)
    return zoom
  def _calc_centering_offset(self, zoom = None):
    if zoom == None:  zoom = self.zoom
    model_box = self.model_bbox
    if model_box == None:
      return (0, 0)

    model_x1, model_y1, model_x2, model_y2 = model_box
    model_w = model_x2 - model_x1
    model_h = model_y2 - model_y1
    vis_x1, vis_y1, vis_x2, vis_y2 = self.visible_bbox
    vis_w = vis_x2 - vis_x1
    vis_h = vis_y2 - vis_y1

    offsetx = model_x1*zoom - (vis_w - model_w*zoom) / 2.0
    offsety = model_y1*zoom - (vis_h - model_h*zoom) / 2.0
    return (offsetx, offsety)

  #### Event handlers

  def handle_resize(self, event):
    self.canvas.update_layer(self)

  def handle_model_event(self, event):
    event_data = utils.event_data_retrieve(event.state)
    if event_data != None:
      if self.model != event_data['model']:  return
      dirty_gridcoords = event_data['dirty_gridcoords']
    else:
      dirty_gridcoords = list(self.points_iterator())

    self.add_particles_at(dirty_gridcoords)
    dirty_particles = [self.get_particle_at(gc) for gc in dirty_gridcoords if self.point_drawn(gc)]
    print 'updating', len(dirty_particles), 'dirty particles of', len(dirty_gridcoords), 'dirty gridcoords'

    self.mark_dirty(dirty_particles)
    self.canvas.update_layer(self)


class SelectLayer(ViewLayer):

  def __init__(self, canvas, model = None, coordinates = None, **kargs):
    ViewLayer.__init__(self, canvas, model, viewmode = 'scroll', **kargs)

    self._coordinates = coordinates

    # Initialize to empty selection
    self._selected = set([]) # Currently selected particles

    ## Add basic event handlers
    self.add_event_handler(self.running_event_handlers, '<ButtonPress-1>', self.handle_leftpress)
    self.add_event_handler(self.running_event_handlers, '<ButtonPress-2>', self.handle_rightpress)

  #### Selection info

  @property
  def selected(self):
    return self._selected
  @selected.setter
  def selected(self, selected):
    self.mark_dirty(self._selected ^ selected)
    self._selected = selected

  #### Selection utilities
  def new_selection(self, particles, append = False):
    if append:
      self.selected += set(particles)
    else:
      self.selected = set(particles)
  def box_selection(self, particles, append = False):
    box = self.model.grid.calc_bbox([p.gridcoord for p in particles])
    box_particles = set([self.get_particle_at(gc) for gc in self.model.grid.points_iterator(box)])
    #print box, box_particles
    self.new_selection(box_particles, append)
  def body_selection(self, particle, append = False):
    particles = self._calc_connected_body_particles(particle)
    self.new_selection(particles, append)
  def toggle_selection(self, particles):
    # unused... remove this function?
    remove = set([])
    add = set([])
    for particle in particles:
      if self.particle_selected(particle):
        remove.add(particle)
      else:
        add.add(particle)
    self.selected = self._selected - remove
    self.selected = self._selected | add

  def merge(self, layer):
    dirty_gridcoords = list(layer.merge_coordinates())
    
    new_selection = []
    for gc in dirty_gridcoords:
      model_p = layer.model.get_particle(gc)
      p = DrawnParticle(gridcoord = gc, oval_id = None, model_particle = model_p)
      self.set_particle_at(gc, p)
      #print gc, model_p
    
    if isinstance(layer, SelectLayer):
      selected_gc = [p.gridcoord for p in layer.selected]
      self.add_particles_at(selected_gc)
      self.selected = set([self.get_particle_at(gc) for gc in selected_gc])
      
    key = utils.event_data_register(dict(model = self.model, dirty_gridcoords = dirty_gridcoords))
    self.canvas.event_generate('<<Model>>', state = key, when = 'tail')

    print 'particles changed in merge:',len(dirty_gridcoords)


  #### Drawing functionality
  def update_particle(self, p):
    """ Updates the location/size of the single given particle on the canvas.
    Extends ViewLayer.update_particle()
    TODO: This might be easier/more elegant if we used tags. """
    ViewLayer.update_particle(self, p)

    if self.particle_selected(p):
      oval_id = p.oval_id
      self.canvas.tag_raise(oval_id, 'particle')



  #### Particle information
  def points_iterator(self):
    if self._coordinates == None:
      return ViewLayer.points_iterator(self)
    else:
      return iter(self._coordinates)

  def particle_selected(self, p):
    return p in self._selected
  def point_hidden(self, gridcoord):
    return gridcoord in self.points_iterator()
  def point_selected(self, gridcoord):
    return self.point_drawn(gridcoord) and self.particle_selected(self.get_particle_at(gridcoord))

  def particle_params(self, particle):
    """ Returns characteristics of the oval corresponding to the given drawn particle.
    Extends ViewLayer.particle_params to give selected particles a thicker border.
    Note that this modifies the behavior of ViewLayer.update_particle(), which calls this function
    to determine the drawing parameters of the oval. """
    params = ViewLayer.particle_params(self, particle)
    if self.particle_selected(particle):
      params['width'] = 4
    return params

  #### Event handlers
  def handle_leftpress(self, event):
    canvaspixel = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    gridcoord = self.model.grid.pixel_to_grid_coord(canvaspixel, self.diameter)
    particle = self.get_particle_at(gridcoord)
    if not self.particle_selected(particle):
      self.new_selection([particle])
  def handle_rightpress(self, event):
    canvaspixel = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    gridcoord = self.model.grid.pixel_to_grid_coord(canvaspixel, self.diameter)
    particle = self.get_particle_at(gridcoord)
    if event.state & MOD_CTRL:
      self.body_selection(particle, event.state & MOD_SHIFT)
    elif event.state & MOD_SHIFT:
      self.box_selection(list(self.selected) + [particle])
    else:
      self.new_selection([particle])
    #self.update() # TODO: change this to self.canvas.update_layer(self)
    self.canvas.update_layer(self)



class EditBasicLayer(SelectLayer):

  def __init__(self, canvas, model = None, coordinates = None, **kargs):
    SelectLayer.__init__(self, canvas, model, coordinates, **kargs)

    ## Set up edit functionality

    # Initialize to erasing brush
    self._brush = None

    ## Add basic event handlers
    # Link virtual events to key-presses (conceivably, we could use different keypresses for Mac/Windows)
    self.canvas.event_add('<<LayerMerge>>', '<Return>')
    self.canvas.event_add('<<LayerCancel>>', '<Escape>')
    self.canvas.event_add('<<Paint>>', '<ButtonRelease-1>')
    self.canvas.event_add('<<Move>>', '<B1-Motion>')
    self.canvas.event_add('<<Undo>>', '<Command-z>')
    self.canvas.event_add('<<Copy>>', '<Command-c>')
    self.canvas.event_add('<<Cut>>', '<Command-x>')
    self.canvas.event_add('<<Paste>>', '<Command-v>')
    self.canvas.event_add('<<Rotate>>', '<Command-r>')
    self.canvas.event_add('<<Flip>>', '<Command-f>')

    self.add_event_handler(self.running_event_handlers, '<<LayerMerge>>', self.handle_layermerge)
    self.add_event_handler(self.running_event_handlers, '<<LayerCancel>>', self.handle_layercancel)
    self.add_event_handler(self.running_event_handlers, '<<Paint>>', self.handle_paint)
    self.add_event_handler(self.running_event_handlers, '<<Move>>', self.handle_move)
    self.add_event_handler(self.running_event_handlers, '<<Undo>>', self.handle_undo, 'all')
    self.add_event_handler(self.running_event_handlers, '<<Copy>>', self.handle_copy, 'all')
    self.add_event_handler(self.running_event_handlers, '<<Cut>>', self.handle_cut, 'all')
    self.add_event_handler(self.running_event_handlers, '<<Paste>>', self.handle_paste, 'all')
    self.add_event_handler(self.running_event_handlers, '<<Rotate>>', self.handle_rotate, 'all')
    self.add_event_handler(self.running_event_handlers, '<<Flip>>', self.handle_flip, 'all')

    self.add_event_handler(self.alive_event_handlers, '<<Brush>>', self.handle_brush_event, 'all')
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
        model_particle = self.model.get_particle(p.gridcoord)
        if brush.particle_specs != None:  model_particle.particle_specs = brush.particle_specs
        if brush.body_specs != None:  model_particle.body_specs = brush.body_specs
      elif create and not p.in_model:
        self.model.add_particle(p.gridcoord, brush.particle_specs, brush.body_specs)
    self.mark_dirty(particles)
    
    ### Emit model-changed event
    gridcoords = [p.gridcoord for p in particles]
    key = utils.event_data_register(dict(dirty_gridcoords = gridcoords, model = self.model))
    self.canvas.event_generate('<<Model>>', state=key, when='tail')

  #### Event handlers

  def handle_brush_event(self, event):
    self.brush = utils.event_data_retrieve(event.state)

  def handle_layermerge(self, event):
    print 'layermerge'

  def handle_layercancel(self, event):
    print 'layercancel'

  def handle_paint(self, event):
    pos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    gridcoord = self.model.grid.pixel_to_grid_coord(pos, self.diameter)
    particle = self.get_particle_at(gridcoord)
    brush = self._brush
    if not self.particle_selected(particle):
      self.new_selection([particle])

    self.apply_brush(brush, self._selected)
    self.canvas.update_layer(self)

  def handle_move(self, event):
    print 'move'
    model = Model(grid_type = self.model.grid.grid_type)
    model.particles = [p.model_particle for p in self.selected if p.in_model]
    coordinates = [p.gridcoord for p in self.selected]
    startpos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    layer = MoveLayer(self.canvas, model, coordinates, startpos = startpos)
    self.canvas.start_layer(layer)
    '''if self.cur_operation == None:
      startpos = (event.x, event.y)
      if self.normal_mode():
        particles = self.selected
      else:
        particles = self.cut
      self.cur_operation = MCO_Move(self, particles, startpos = startpos)

    self.cur_operation.set_duplicating(event.state & MOD_SHIFT)
    self.cur_operation.drag((event.x, event.y))
    self.update()'''

  def handle_moveend(self, event):
    print 'moveend'
    '''self.cur_operation.set_duplicating(event.state & MOD_SHIFT)
    self.apply_current_operation()
    self.update()'''

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


class EditBackgroundLayer(EditBasicLayer):

  def __init__(self, canvas, model = None, coordinates = None, **kargs):
    EditBasicLayer.__init__(self, canvas, model, **kargs)

  def update_view_scroll(self):
    EditBasicLayer.update_view_scroll(self)
    self.add_particles_at(self.points_iterator())


  #### Particle information

  def points_iterator(self):
    """ Returns an iterator over all points that must be drawn on the canvas.
    In this case, this is all points within the scrollable bounding box."""
    if self.model == None:
      return iter([])
    else:
      box = self.model.grid.pixel_to_grid_coord_bbox(self.scrollable_bbox, self.diameter)
      return self.model.grid.points_iterator(box)
  def particle_hidden(self, p):
    return False
  def point_hidden(self, gridcoord):
    return False

class MoveLayer(SelectLayer):

  def __init__(self, canvas, model, coordinates, startpos, **kargs):
    SelectLayer.__init__(self, canvas, model, coordinates, **kargs)

    self._startpos = startpos
    self._offset = (0, 0)

    self._duplicating = False

    self._moving_tag = '{0}_moving'.format(repr(self))
    self._stationary_tag = '{0}_stationary'.format(repr(self))

    self._gridcoord_to_particle_moving = dict() # originally selected particles being moved
    self._gridcoord_to_particle_stationary = dict() # new particles placed in the old locations of the originals

    self.add_event_handler(self.running_event_handlers, '<B1-Motion>', self.handle_drag)
    self.add_event_handler(self.running_event_handlers, '<ButtonRelease-1>', self.handle_release)

  def set_model(self, model):
    assert False, "Cannot set the model of a MoveLayer after instantiation"

  def add_particle_at(self, gridcoord):
    oval_id_stationary = self.canvas.create_oval(0, 0, 0, 0, tags = ('particle', self._stationary_tag), state = tk.HIDDEN)
    oval_id_moving = self.canvas.create_oval(0, 0, 0, 0, tags = ('particle', self._moving_tag), state = tk.HIDDEN)

    model_p = self.model.get_particle(gridcoord)
    moving = DrawnParticle(gridcoord = gridcoord, oval_id = oval_id_moving, model_particle = model_p)
    stationary = DrawnParticle(gridcoord = gridcoord, oval_id = oval_id_stationary, model_particle = None)

    self._gridcoord_to_particle_moving[gridcoord] = moving
    self._gridcoord_to_particle_stationary[gridcoord] = stationary
    self.mark_dirty([moving, stationary])
    return moving
  def get_moving_particle_at(self, gridcoord):
    return self._gridcoord_to_particle_moving[gridcoord]
  def get_stationary_particle_at(self, gridcoord):
    return self._gridcoord_to_particle_stationary[gridcoord]
  def get_particle_at(self, gridcoord):
    return self.get_moving_particle_at(gridcoord)
  def set_particle_at(self, gridcoord, p):
    assert False, 'unsupported'

  ## start(), pause(), resume() inherited from SelectLayer

  def start(self):
    SelectLayer.start(self)

    self.canvas.tag_lower(self._stationary_tag, self._moving_tag)
    self.selected = set(self.moving_particles_iterator())
    
  def merge(self):
    assert False, "Merging unsupported with MoveLayer"
  def merge_coordinates(self):
    return [p.gridcoord for p in self.particles_iterator()]

  def finish(self):
    SelectLayer.finish(self)

    offset = self._offset_rounded()
      
    for p in self.stationary_particles_iterator():
      if not self._duplicating or p.model_particle == None:
        self.model.remove_particle(p.gridcoord)
      else:
        self.model.set_particle(p.gridcoord, p.model_particle)

    for p in self.moving_particles_iterator():
      self._move_particle(p, offset)
      if p.model_particle == None:
        self.model.remove_particle(p.gridcoord)
      else:
        self.model.set_particle(p.gridcoord, p.model_particle)

    self.canvas.update_layer(self)

  ## cancel(), clean() inherited from SelectLayer

  #def update(self):

  #def submit(self):
  #  offset = self._offset_rounded()
  #    
  #  for p in self.stationary_particles_iterator():
  #    if not self._duplicating:
  #      self.model.remove_particle(p.gridcoord)
  #    else:
  #      self.model.set_particle(p.gridcoord, p.model_particle)#

  #  for p in self.moving_particles_iterator():
  #    self._move_particle(p, offset)
  #    self.model.set_particle(p.gridcoord, p.model_particle)

  #def cancel(self):
  #  self._delete_duplicates()
  #  return []

  #def get_oval_coords(self, p):
  #  coords = self.model_canvas._get_oval_coords(p)
  #  if not self._is_duplicate(p):
  #    offset = self._offset_rounded()
  #    coords = (coords[0] + offset[0], coords[1] + offset[1],
  #        coords[2] + offset[0], coords[3] + offset[1])
  #  return coords
  #def get_oval_characteristics(self, p):
  #  return self.model_canvas._get_oval_characteristics(p)

  #def drag(self, pos):
  #  startpos = self.args['startpos']
  #  self.offset = (pos[0] - startpos[0], pos[1] - startpos[1])
  #  #print self.offset, self.args['duplicating']
  #  self.model_canvas.mark_dirty(self.particles)

  def particles_iterator(self):
    """ Returns an iterator over all particles being drawn in this layer."""
    return itertools.chain(self._gridcoord_to_particle_moving.itervalues(), self._gridcoord_to_particle_stationary.itervalues())
  def moving_particles_iterator(self):
    return self._gridcoord_to_particle_moving.itervalues()
  def stationary_particles_iterator(self):
    return self._gridcoord_to_particle_stationary.itervalues()


  def point_hidden(self, gc):
    return False
  def point_drawn(self, gc):
    return gc in self._gridcoord_to_particle_moving and gc in self._gridcoord_to_particle_stationary
  def particle_hidden(self, p):
    return not self._duplicating and self.particle_stationary(p)
  def particle_moving(self, p):
    return self._moving_tag in self.canvas.gettags(p.oval_id)
  def particle_stationary(self, p):
    return self._stationary_tag in self.canvas.gettags(p.oval_id)


  def particle_coords(self, p):
    coords = SelectLayer.particle_coords(self, p)
    if self.particle_moving(p):
      offset = self._offset_rounded()
      coords = (coords[0] + offset[0], coords[1] + offset[1],
          coords[2] + offset[0], coords[3] + offset[1])
    return coords



  def handle_drag(self, event):
    posx = self.canvas.canvasx(event.x)
    posy = self.canvas.canvasy(event.y)
    self._offset = (posx - self._startpos[0], posy - self._startpos[1])
    
    self._set_duplicating(event.state & MOD_SHIFT)

    self.mark_dirty(self.moving_particles_iterator())
    self.canvas.update_layer(self)

  def handle_release(self, event):
    if self._offset == (0, 0):
      self.canvas.cancel_top_layer()
    else:
      self.canvas.merge_top_layer()


  #def _make_particles(self):
  #  for model_p in self.model.particles:
  #    gc = model_p.grid_coord
  #    self.add_particle_at(gc)
  #  self.canvas.tag_lower(self._stationary_tag, self._moving_tag)
  #  self.selected = set(self.moving_particles_iterator())
      #self.model_canvas.tag_lower(new_p.oval_id, p.oval_id)
    #self.duplicates = set(self.duplicates_dict.itervalues())
    #self.model_canvas.mark_dirty(self.duplicates)
  #def _delete_particles(self):
  #  self.model_canvas.delete(self._moving_tag)
  #  self.model_canvas.delete(self._stationary_tag)

  #def _is_duplicate(self, p):
  #  return p in self.duplicates


  def _set_duplicating(self, duplicating):
    if self._duplicating != duplicating:
      self._duplicating = duplicating
      self.mark_dirty(set(self.stationary_particles_iterator()))

  def _offset_rounded(self):
    diameter = self.diameter
    grid = self.model.grid

    startpos = self._startpos
    finalpos = (startpos[0] + self._offset[0], startpos[1] + self._offset[1])
    startpos_rounded = grid.grid_coord_to_pixel(grid.pixel_to_grid_coord(startpos, diameter), diameter)
    finalpos_rounded = grid.grid_coord_to_pixel(grid.pixel_to_grid_coord(finalpos, diameter), diameter)
    offset = (finalpos_rounded[0] - startpos_rounded[0], finalpos_rounded[1] - startpos_rounded[1])
    return offset

  def _move_particle(self, p, offset):
    diameter = self.diameter
    grid = self.model.grid

    old_pos = grid.grid_coord_to_pixel(p.gridcoord, diameter)
    new_pos = (old_pos[0] + offset[0], old_pos[1] + offset[1])
    new_gc = grid.pixel_to_grid_coord(new_pos, diameter)
    p.gridcoord = new_gc

