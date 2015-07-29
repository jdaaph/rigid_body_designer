import grid
from copy import deepcopy

class Model(object):
  """ Model implements an object that stores points in a "model", or collection of points of various particle types
  and/or rigid body assignments. The Model class stores a grid that determines how the grid coordinate corresponding
  to each point is converted to a pixel.
  Point information is stored in Particle objects, which are created and deleted as particles are added and removed
  from the model. A Particle object relates a grid coordinate to a particle type and body type, represented as
  ParticleSpecs and BodySpecs objects, respectively.
  Externally, most interactions with the Model do not directly access Particle objects, instead using grid coordinates
  to refer to locations in the Model that may or may not have an associated particle.
  The Model implements the following functionality:
    - Allows particles to be added to the model with add_particle()
    - Allows particles to be removed from the model with remove_particle()
    - Query if a particle is in the model with has_particle()
    - Modify particles with set_particle_type() and set_body_type()
    - Query particle information with get_particle_type() and get_particle_type()
    - Calculate a bounding box (in grid coordinates) over all grid coordinates in the model
    - Get an iterator over all grid coordinates in the model
    - Access the underlying grid object for grid coordinate/pixel conversions (model.grid)
  """
  _grid = None
  
  _particles = None

  grid_coord_to_particle = None

  def __init__(self, grid_type = grid.GRID_SQUARE):
    ## Initialize to having no particles in model
    self._particles = set([])
    self.grid_coord_to_particle = dict()

    ## Initialize grid
    self.init_grid(grid_type)

  @property
  def particles(self):
    return list(self._particles)

  @particles.setter
  def particles(self, new_particles):
    self._particles.clear()
    self.grid_coord_to_particle.clear()

    for new_p in new_particles:
      self.add_particle(new_p.grid_coord, new_p.particle_specs, new_p.body_specs)

  def point_iterator(self):
    return iter(self._particles)

  @property
  def grid(self):
    return self._grid

  def init_grid(self, grid_type):
    """ Initializes the grid to a minimum size."""
    if grid_type == grid.GRID_SQUARE:
      self._grid = grid.SquareGrid()
    else:
      assert False, "Grid type {0} not supported.".format(grid_type)

  def add_particle(self, grid_coord, particle_specs, body_specs):
    """ Add a new particle to the model with the given ParticleSpecs and BodySpecs objects.
    If there is already a particle at this coordinate, the existing particle's particle
    and body types are set to the given ParticleSpecs and BodySpecs objects.  """
    if not self.has_particle(grid_coord):
      particle = Particle(grid_coord, particle_specs, body_specs)
      self.grid_coord_to_particle[grid_coord] = particle
      self._particles.add(particle)
    else:
      particle = self.grid_coord_to_particle[grid_coord]
      particle.particle_specs = particle_specs
      particle.body_specs = body_specs
    return particle
  def remove_particle(self, grid_coord):
    """ Remove a given particle from the model, if it is in there.
    This method does nothing if the particle was not in the model """
    if self.has_particle(grid_coord):
      p = self.grid_coord_to_particle[grid_coord]
      self.grid_coord_to_particle.remove(grid_coord)
      self._particles.remove(p)
  def has_particle(self, grid_coord):
    """ Returns True iff there is a particle in the model at the given grid coordinate. """
    return grid_coord in self.grid_coord_to_particle

  def get_particle_type(self, grid_coord):
    """ Returns the ParticleSpecs object for the particle at the given grid coordinate,
    or None if no particle exists there. """
    if self.has_particle(grid_coord):
      return self.grid_coord_to_particle[grid_coord].particle_specs
    else:
      return None
  def get_body_type(self, grid_coord):
    """ Returns the BodySpecs object for the particle at the given grid coordinate,
    or None if no particle exists there. """
    if self.has_particle(grid_coord):
      return self.grid_coord_to_particle[grid_coord].body_specs
    else:
      return None

  def set_particle_type(self, grid_coord, particle_specs):
    if self.has_particle(grid_coord):
      self.grid_coord_to_particle[grid_coord].particle_specs = particle_specs
  def set_body_type(self, grid_coord, body_specs):
    if self.has_particle(grid_coord):
      self.grid_coord_to_particle[grid_coord].body_specs = body_specs

  def calc_connected_body_particles(self, grid_coord):
    '''returns a list of particles in the same body as particle'''
    body = particle.body_specs
    buddies = []
    for ite in self.particles:
      if ite.body_specs == body and ite.present: 
        buddies.append(ite)
    return buddies

  def calc_bbox(self):
    return self.grid.calc_bbox([p.grid_coord for p in self._particles])

class Particle(object):
  grid_coord = None

  particle_specs = None
  body_specs = None
  def __init__(self, grid_coord, particle_specs, body_specs):
    self.grid_coord = grid_coord

    self.particle_specs = particle_specs
    self.body_specs = body_specs

  def copy(self):
    new_par = deepcopy(self)
    new_par.particle_specs = self.particle_specs
    new_par.body_specs = self.body_specs
    return new_par
