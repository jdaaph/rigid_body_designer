import Tkinter as tk

import itertools

from copy import deepcopy

import utils
from model import Model
from particle import Particle, DrawnParticle

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
  start_coordinates(), finish_coordinates()
    Because a layer can be viewed as operating on a set of particles, it is sometimes
    useful during a merge operation to determine the original coordinates and final coordinates
    handled by the layer. In general, the locations in finish_coordinates() are the ones that
    will be merged into the parent layer when merge() is called.
    Should only be called after finish() or cancel() has been executed.
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
  def start_coordinates(self):
    return []
  def finish_coordinates(self):
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
  def stop_event_handler(self, event, funcid, tag):
    """Unbind for this widget for event SEQUENCE  the function identified with FUNCID.
    Adapted from
    http://stackoverflow.com/questions/6433369/deleting-and-changing-a-tkinter-event-binding-in-python
    to work around the Tkinter unbind bug. """
    w = self.canvas
    if tag == None:  tag = w._w
    old_callbacks = w.tk.call('bind', tag, event, None).split('\n')
    new_callbacks = [l for l in old_callbacks if l.find(funcid) == -1]
    w.tk.call('bind', tag, event, '\n'.join(new_callbacks))
    w.deletecommand(funcid)
  def add_event_handler(self, handler_list, event, handler, tag = None):
    # TODO -- maybe have an EventInfo class instead of a list?
    handler_list.append([event, handler, tag, None])
  def stop_event_handlers(self, handler_list):
    for event_info in handler_list:
      ## event_info is list [event, handler, tag, funcid]
      event, handler, tag, funcid = event_info
      #self.canvas.unbind(event, funcid)
      self.stop_event_handler(event, funcid, tag)
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

  def __init__(self, canvas, model = None, points = None, viewmode = 'auto'):
    ModelCanvasLayer.__init__(self, canvas, model)

    # Set up set of points (grid coords) drawn in this layer
    if points != None:  self.points = set(points)
    elif model != None:  self.points = set([p.gridcoord for p in model.particles])
    else:  self.points = set([])
    self._init_points = frozenset(self.points)
    #assert all([not isinstance(p, Particle) for p in self.points]), '__init__(): invalid points given'

    # Set up dict to map between drawn particles and grid coordinates
    self._gridcoord_to_particle = dict()

    self._diameter = 20.0 ## diameter of spheres, in unzoomed distance units (pixels?)
    self._zoom = 1.0 ## Zoom level (1 = no zoom)
    self._padding = 10 ## Padding to surround model with, in units of cell diameter

    self._dirty = set([])

    self.viewmode = viewmode

    if self.canvas['scrollregion'] == '':
      self.canvas['scrollregion'] = (0, 0, 0, 0)
    
    self.add_event_handler(self.alive_event_handlers, '<Configure>', self.handle_resize)
    self.add_event_handler(self.alive_event_handlers, '<<Model>>', self.handle_model_event, 'all')

    # Tags for particle manipulation
    self._universal_tag = 'MCL_object'
    self._tag = repr(self)
    self._running_tag = repr(self) + "_running"

  #### General properties

  @property
  def model(self):
    return self._model
  def set_model(self, model):
    self._model = model
    if model != None:  self.points |= set(model.points_iterator())
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
    box = self.model.grid.gridcoord_to_pixel_bbox(self.model.calc_bbox(), self.diameter)
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

    self.canvas.addtag_withtag(self._running_tag, self._tag)
    self.mark_dirty(particles)
    self.canvas.update_layer(self)

  def merge(self, layer):
    assert False, "Editing is not permitted with ViewBaseLayer"
  def start_coordinates(self):
    return self._init_points
  def finish_coordinates(self):
    return self.points

  def pause(self):
    ModelCanvasLayer.pause(self)
    self.canvas.dtag(self._tag, self._running_tag)
    self.mark_dirty(self.particles_iterator())
    self.canvas.update_layer(self)

  def resume(self):
    ModelCanvasLayer.resume(self)
    self.canvas.addtag_withtag(self._running_tag, self._tag)
    self.mark_dirty(self.particles_iterator())
    self.canvas.update_layer(self)

  def finish(self):
    ModelCanvasLayer.finish(self)
    self.canvas.dtag(self._tag, self._running_tag)
  def cancel(self):
    ModelCanvasLayer.cancel(self)
    self.canvas.dtag(self._tag, self._running_tag)

  def clean(self):
    ModelCanvasLayer.clean(self)
    self.canvas.delete(self._tag)
    #for p in self.particles_iterator():
    #  self.canvas.delete(p.oval_id)


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
    #if self.canvas.find_withtag(self._universal_tag) != ():  self.canvas.tag_raise(self._running_tag, self._universal_tag)
    self.canvas.tag_raise(self._running_tag)
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
    oval_id = self.canvas.create_oval(0, 0, 0, 0, tags = ('particle', self._tag, self._universal_tag), state = tk.HIDDEN)

    model_p = self.model.get_particle(gridcoord)
    p = DrawnParticle(gridcoord = gridcoord, oval_id = oval_id, model_particle = model_p)
    self._gridcoord_to_particle[gridcoord] = p
    return p
  def remove_particle_at(self, gridcoord):
    self.model.remove_particle(gridcoord)
    self.points.remove(gridcoord)
  def get_particle_at(self, gridcoord):
    return self._gridcoord_to_particle[gridcoord]
  def set_particle_at(self, gridcoord, p):
    old = self.get_particle_at(gridcoord) if self.point_drawn(gridcoord) else self.add_particle_at(gridcoord)
    old.model_particle = p.model_particle
    if old.model_particle == None:
      self.model.remove_particle(gridcoord)
    else:
      self.model.set_particle(gridcoord, old.model_particle)
    self.points.add(gridcoord)
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
  def remove_particles_at(self, gridcoords):
    for gridcoord in set(gridcoords):
      self.remove_particle_at(gridcoord)



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
    #assert all([not isinstance(p, Particle) for p in self.points]), 'points_iterator(): invalid points given'
    return iter(self.points)
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
    return self.point_hidden(p.gridcoord)
  def point_in_model(self, gridcoord):
    return self.model.has_particle(gridcoord)
  def point_hidden(self, gridcoord):
    return gridcoord not in self.points
  def point_drawn(self, gridcoord):
    return gridcoord in self._gridcoord_to_particle

  def particle_coords(self, p):
    """ Returns the coordinates of the drawn particle as a tuple. Set the oval coordinates with
    coords(oval_id, *coords) """
    ## Calculate shape location
    diameter = self.diameter
    canvas_x0, canvas_y0 = self.model.grid.gridcoord_to_pixel(p.gridcoord, diameter)
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
    print 'modelevent', repr(self)

    self.points -= set(filter(lambda gc: not self.model.has_particle(gc), dirty_gridcoords))
    self.points |= set(filter(lambda gc: self.model.has_particle(gc), dirty_gridcoords))
    self.add_particles_at(dirty_gridcoords)
    dirty_particles = [self.get_particle_at(gc) for gc in dirty_gridcoords if self.point_drawn(gc)]
    print 'updating', len(dirty_particles), 'dirty particles of', len(dirty_gridcoords), 'dirty gridcoords'

    self.mark_dirty(dirty_particles)
    self.canvas.update_layer(self)


class SelectLayer(ViewLayer):

  def __init__(self, canvas, model = None, points = None, **kargs):
    ViewLayer.__init__(self, canvas, model, points, viewmode = 'scroll', **kargs)

    # Initialize to empty selection
    self._selected = set([]) # Currently selected particles

    ## Define events
    self.canvas.event_add('<<SelectAll>>', '<Command-a>')

    ## Add basic event handlers
    self.add_event_handler(self.running_event_handlers, '<ButtonPress-1>', self.handle_leftpress)
    self.add_event_handler(self.running_event_handlers, '<ButtonPress-2>', self.handle_rightpress)
    self.add_event_handler(self.running_event_handlers, '<<SelectAll>>', self.handle_selectall)

  #### Selection info

  #def set_model(self, model):
  #  ViewLayer.set_model(self, model)

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
      self.selected |= set(particles)
    else:
      self.selected = set(particles)
  def remove_selection(self, particles):
    self.selected -= set(particles)
  def box_selection(self, particles, append = False):
    box = self.model.grid.calc_bbox([p.gridcoord for p in particles])
    box_particles = set([self.get_particle_at(gc) for gc in self.model.grid.points_iterator(box) if not self.point_hidden(gc)])
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
  def clear_selection(self):
    self.new_selection([])

  def start(self):
    ViewLayer.start(self)

    self.add_particles_at(self.points)
    self.new_selection([self.get_particle_at(gc) for gc in self.points])
    self.canvas.update_layer(self)


  #### Drawing functionality
  def update_particle(self, p):
    """ Updates the location/size of the single given particle on the canvas.
    Extends ViewLayer.update_particle()
    TODO: This might be easier/more elegant if we used tags. """
    ViewLayer.update_particle(self, p)

    if self.particle_selected(p):
      oval_id = p.oval_id
      self.canvas.tag_raise(oval_id, 'particle')

  def remove_particle_at(self, gridcoord):
    ViewLayer.remove_particle_at(self, gridcoord)
    if self.point_selected(gridcoord):
      self.remove_selection([self.get_particle_at(gridcoord)])


  #### Particle information
  def particle_selected(self, p):
    return p in self._selected
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
    gridcoord = self.model.grid.pixel_to_gridcoord(canvaspixel, self.diameter)
    if self.point_hidden(gridcoord):
      self.clear_selection()
    else:
      particle = self.get_particle_at(gridcoord)
      if not self.particle_selected(particle):
        self.new_selection([particle])
  def handle_rightpress(self, event):
    canvaspixel = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    gridcoord = self.model.grid.pixel_to_gridcoord(canvaspixel, self.diameter)
    #print canvaspixel, gridcoord
    if self.point_hidden(gridcoord):
      self.clear_selection()
    else:
      particle = self.get_particle_at(gridcoord)
      if event.state & MOD_CTRL:
        self.body_selection(particle, event.state & MOD_SHIFT)
      elif event.state & MOD_SHIFT:
        self.box_selection(list(self.selected) + [particle])
      else:
        self.new_selection([particle])

    self.canvas.update_layer(self)

  def handle_selectall(self, event):
    self.add_particles_at(self.points)
    self.new_selection([self.get_particle_at(gc) for gc in self.points])

    self.canvas.update_layer(self)



class EditBasicLayer(SelectLayer):

  def __init__(self, canvas, model = None, coordinates = None, **kargs):
    SelectLayer.__init__(self, canvas, model, coordinates, **kargs)

    ## Set up edit functionality

    # Initialize to erasing brush
    self._brush = None

    # For storing copied particles
    self.clipboard_data = None

    ## Add basic event handlers
    # Link virtual events to key-presses (conceivably, we could use different keypresses for Mac/Windows)
    self.canvas.event_add('<<LayerMerge>>', '<Return>')
    self.canvas.event_add('<<LayerCancel>>', '<Escape>')
    self.canvas.event_add('<<Paint>>', '<ButtonPress-1><ButtonRelease-1>')
    self.canvas.event_add('<<Move>>', '<ButtonPress-1><B1-Motion>')
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
    self.add_event_handler(self.running_event_handlers, '<<Undo>>', self.handle_undo)
    self.add_event_handler(self.running_event_handlers, '<<Copy>>', self.handle_copy)
    self.add_event_handler(self.running_event_handlers, '<<Cut>>', self.handle_cut)
    self.add_event_handler(self.running_event_handlers, '<<Paste>>', self.handle_paste)
    self.add_event_handler(self.running_event_handlers, '<<Rotate>>', self.handle_rotate)
    self.add_event_handler(self.running_event_handlers, '<<Flip>>', self.handle_flip)

    self.add_event_handler(self.alive_event_handlers, '<<Brush>>', self.handle_brush_event, 'all')
    self.add_event_handler(self.alive_event_handlers, '<<Clipboard>>', self.handle_clipboard_event, 'all')
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

  #### Layer functionality

  def merge(self, layer):
    start_gc = set(layer.start_coordinates())
    finish_gc = set(layer.finish_coordinates())
    dirty_gc = start_gc | finish_gc
    
    # Transfer information at these locations from the merged layer
    self.remove_particles_at(start_gc)
    # Add particles in the final operation state
    self.points |= finish_gc
    for gc in finish_gc:
      model_p = layer.model.get_particle(gc)
      p = DrawnParticle(gridcoord = gc, oval_id = None, model_particle = model_p)
      self.set_particle_at(gc, p)
      #print gc, model_p

    # Transfer the selection to the parent layer
    if isinstance(layer, SelectLayer):
      selected_gc = set([p.gridcoord for p in layer.selected])
      dirty_gc |= selected_gc
      self.add_particles_at(selected_gc)
      self.selected = set([self.get_particle_at(gc) for gc in selected_gc])
      
    key = utils.event_data_register(dict(model = self.model, dirty_gridcoords = dirty_gc))
    self.canvas.event_generate('<<Model>>', state = key, when = 'tail')

    print 'particles changed in merge:',len(dirty_gc)

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

  def handle_clipboard_event(self, event):
    print 'clipboard'
    self.clipboard_data = utils.event_data_retrieve(event.state)

  def handle_layermerge(self, event):
    print 'layermerge'
    self.canvas.merge_top_layer()

  def handle_layercancel(self, event):
    print 'layercancel'
    self.canvas.cancel_top_layer()

  def handle_paint(self, event):
    pos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    gridcoord = self.model.grid.pixel_to_gridcoord(pos, self.diameter)
    if self.point_hidden(gridcoord):
      return
    particle = self.get_particle_at(gridcoord)
    brush = self._brush
    if not self.particle_selected(particle):
      self.new_selection([particle])

    self.apply_brush(brush, self._selected)
    self.canvas.update_layer(self)

  def handle_move(self, event):
    print 'move'
    model, coordinates = self.get_operation_particles()
    startpos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
    layer = MoveLayer(self.canvas, model, coordinates, startpos = startpos)
    self.canvas.start_layer(layer)

  def handle_undo(self, event):
    print 'undo'

  def handle_cut(self, event):
    print 'cut'
    if len(self.selected) == 0:
      return
    model, coordinates = self.get_operation_particles()
    layer = EditBasicLayer(self.canvas, model, coordinates)
    layer.brush = self._brush
    self.canvas.start_layer(layer)


  def handle_copy(self, event):
    print 'copy'
    if len(self.selected) == 0:
      return
    model, coordinates = self.get_operation_particles()
    key = utils.event_data_register(dict(model = model, coordinates = coordinates))
    self.canvas.event_generate('<<Clipboard>>', state = key)


  def handle_paste(self, event):
    print 'paste'
    if self.clipboard_data == None:  return
    model = deepcopy(self.clipboard_data['model'])
    coordinates = deepcopy(self.clipboard_data['coordinates'])
    layer = PasteLayer(self.canvas, model, coordinates)
    layer.brush = self._brush
    self.canvas.start_layer(layer)

  def handle_rotate(self, event):
    print 'rotate'
    steps = -1 if event.state & MOD_SHIFT else 1
    model, coordinates = self.get_operation_particles()
    layer = RotateLayer(self.canvas, model, coordinates, steps = steps)
    layer.brush = self._brush
    self.canvas.start_layer(layer)
    

  def handle_flip(self, event):
    print 'flip'
  
  def get_operation_particles(self):
    model = Model(grid_type = self.model.grid.grid_type)
    if len(self.selected) > 0:
      model.particles = [p.model_particle for p in self.selected if p.in_model]
      coordinates = [p.gridcoord for p in self.selected]
    else:
      model.particles = list(self.model.particles)
      coordinates = list(self.points)
    return model, coordinates



class EditBackgroundLayer(EditBasicLayer):

  def __init__(self, canvas, model = None, coordinates = None, **kargs):
    EditBasicLayer.__init__(self, canvas, model, coordinates, **kargs)

  def update_view_scroll(self):
    EditBasicLayer.update_view_scroll(self)
    
    box = self.model.grid.pixel_to_gridcoord_bbox(self.scrollable_bbox, self.diameter)
    self.points |= set(self.model.grid.points_iterator(box))
    self.add_particles_at(self.points)


  #### Particle information
  def particle_hidden(self, p):
    return False
  def point_hidden(self, gridcoord):
    return False

  def handle_layermerge(self, event):
    pass
  def handle_layercancel(self, event):
    pass
  def handle_selectall(self, event):
    self.add_particles_at(self.model.points_iterator())
    self.new_selection([self.get_particle_at(gc) for gc in self.model.points_iterator()])
    self.canvas.update_layer(self)

  def get_operation_particles(self):
    model = Model(grid_type = self.model.grid.grid_type)
    if len(self.selected) > 0:
      model.particles = [p.model_particle for p in self.selected if p.in_model]
      coordinates = [p.gridcoord for p in self.selected]
    else:
      model.particles = list(self.model.particles)
      coordinates = [p.gridcoord for p in model.particles]
    return model, coordinates

class MoveLayer(SelectLayer):

  def __init__(self, canvas, model, points, startpos, **kargs):
    SelectLayer.__init__(self, canvas, model, points, **kargs)

    self._startpos = startpos
    self._offset = (0, 0)

    self._duplicating = False

    self._moving_tag = '{0}_moving'.format(repr(self))
    self._stationary_tag = '{0}_stationary'.format(repr(self))

    self._gridcoord_to_particle_moving = dict() # originally selected particles being moved
    self._gridcoord_to_particle_stationary = dict() # new particles placed in the old locations of the originals

    self.add_event_handler(self.running_event_handlers, '<B1-Motion>', self.handle_drag)
    self.add_event_handler(self.running_event_handlers, '<ButtonRelease-1>', self.handle_release)
    self.add_event_handler(self.running_event_handlers, '<Any-KeyPress>', self.handle_key)
    self.add_event_handler(self.running_event_handlers, '<Any-KeyRelease>', self.handle_key)

  def set_model(self, model):
    assert False, "Cannot set the model of a MoveLayer after instantiation"

  def add_particle_at(self, gridcoord):
    oval_id_stationary = self.canvas.create_oval(0, 0, 0, 0, tags = ('particle', self._tag, self._universal_tag, self._stationary_tag), state = tk.HIDDEN)
    oval_id_moving = self.canvas.create_oval(0, 0, 0, 0, tags = ('particle', self._tag, self._universal_tag, self._moving_tag), state = tk.HIDDEN)

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
  #def merge_coordinates(self):
  #  return [p.gridcoord for p in self.particles_iterator()]

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

    if self._duplicating:
      self.points |= set([p.gridcoord for p in self.moving_particles_iterator()])
    else:
      self.points = set([p.gridcoord for p in self.moving_particles_iterator()])

    self.canvas.update_layer(self)

  ## cancel(), clean(), update() inherited from SelectLayer

  def particles_iterator(self):
    """ Returns an iterator over all particles being drawn in this layer."""
    return itertools.chain(self._gridcoord_to_particle_moving.itervalues(), self._gridcoord_to_particle_stationary.itervalues())
  def moving_particles_iterator(self):
    return self._gridcoord_to_particle_moving.itervalues()
  def stationary_particles_iterator(self):
    return self._gridcoord_to_particle_stationary.itervalues()


  def point_drawn(self, gc):
    return gc in self._gridcoord_to_particle_moving and gc in self._gridcoord_to_particle_stationary
  def particle_hidden(self, p):
    return self.particle_stationary(p) and not self._duplicating
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
    self._set_duplicating(event.state & MOD_SHIFT)
    if self._offset == (0, 0):
      self.canvas.cancel_top_layer()
    else:
      self.canvas.merge_top_layer()

  def handle_key(self, event):
    if event.keysym == 'Escape':
      self.canvas.cancel_top_layer()
    else:
      self._set_duplicating(event.state & MOD_SHIFT)
      self.canvas.update_layer(self)

  def _set_duplicating(self, duplicating):
    if self._duplicating != duplicating:
      self._duplicating = duplicating
      self.mark_dirty(set(self.stationary_particles_iterator()))

  def _offset_rounded(self):
    diameter = self.diameter
    grid = self.model.grid

    startpos = self._startpos
    finalpos = (startpos[0] + self._offset[0], startpos[1] + self._offset[1])
    startpos_rounded = grid.gridcoord_to_pixel(grid.pixel_to_gridcoord(startpos, diameter), diameter)
    finalpos_rounded = grid.gridcoord_to_pixel(grid.pixel_to_gridcoord(finalpos, diameter), diameter)
    offset = (finalpos_rounded[0] - startpos_rounded[0], finalpos_rounded[1] - startpos_rounded[1])
    return offset

  def _move_particle(self, p, offset):
    diameter = self.diameter
    grid = self.model.grid

    old_pos = grid.gridcoord_to_pixel(p.gridcoord, diameter)
    new_pos = (old_pos[0] + offset[0], old_pos[1] + offset[1])
    new_gc = grid.pixel_to_gridcoord(new_pos, diameter)
    p.gridcoord = new_gc

class PasteLayer(EditBasicLayer):

  def __init__(self, canvas, model, points, **kargs):
    EditBasicLayer.__init__(self, canvas, model, points, **kargs)

  def set_model(self, model):
    assert False, "Cannot set the model of a PasteLayer after instantiation"

  ## start(), pause(), resume() inherited from EditBasicLayer

  def start_coordinates(self):
    return []

  ## finish(), cancel(), clean(), update() inherited from EditBasicLayer

class RotateLayer(EditBasicLayer):

  def __init__(self, canvas, model, points, steps = 1, **kargs):
    EditBasicLayer.__init__(self, canvas, model, points, **kargs)

    self._steps = steps

  def set_model(self, model):
    assert False, "Cannot set the model of a RotateLayer after instantiation"

  ## start(), pause(), resume() inherited from EditBasicLayer

  def start(self):
    EditBasicLayer.start(self)

    grid = self.model.grid
    box = grid.gridcoord_to_pixel_bbox(grid.calc_bbox(self.points), self.diameter)
    center_pixel = (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))
    center_gc = grid.pixel_to_gridcoord(center_pixel, self.diameter)
    mapping = grid.rotate_gridcoords(self.points, center_gc, self._steps)
    #print center_gc, mapping
    
    old_particles = {gc: deepcopy(self.get_particle_at(gc)) for gc in self.points}
    old_selection = set([p.gridcoord for p in self.selected])

    self.remove_particles_at(self.points)
    for old_gc, new_gc in mapping.iteritems():
      self.set_particle_at(new_gc, old_particles[old_gc])
      if old_gc in old_selection:
        self.new_selection([self.get_particle_at(new_gc)], append = True)

    self.canvas.update_layer(self)
    #self.canvas.merge_top_layer()

  def finish(self):
    EditBasicLayer.finish(self)

  ## cancel(), clean(), update() inherited from EditBasicLayer