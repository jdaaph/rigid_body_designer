
from copy import deepcopy


class Particle(object):
  grid_coord = None

  particle_specs = None
  body_specs = None
  def __init__(self, grid_coord, particle_specs, body_specs):
    self.grid_coord = grid_coord

    self.particle_specs = particle_specs
    self.body_specs = body_specs
#
#  def copy(self):
#    new_par = deepcopy(self)
#    new_par.particle_specs = self.particle_specs
#    new_par.body_specs = self.body_specs
#    return new_par

  def __deepcopy__(self, memo):
    gc_copy = deepcopy(self.grid_coord, memo)
    pspecs_copy = deepcopy(self.particle_specs, memo)
    bspecs_copy = deepcopy(self.body_specs, memo)
    return Particle(gc_copy, pspecs_copy, bspecs_copy)


class DrawnParticle(object):
  def __init__(self, gridcoord, oval_id, model_particle = None):
    ## Particle parameters
    self._gridcoord = gridcoord
    self.oval_id = oval_id
    self._particle = deepcopy(model_particle)

  @property
  def model_particle(self):
    return self._particle
  @model_particle.setter
  def model_particle(self, p):
    self._particle = deepcopy(p)
    #self.in_model = p != None
    assert (self._particle!=None) == self.in_model

  @property
  def in_model(self):
    return self._particle != None

  @property
  def gridcoord(self):
    return self._gridcoord
  @gridcoord.setter
  def gridcoord(self, gc):
    assert (self._particle!=None) == self.in_model
    self._gridcoord = gc
    if self.in_model:
      self._particle.grid_coord = gc

  @property
  def particle_specs(self):
    return self._particle.particle_specs if self.in_model else None
  @particle_specs.setter
  def particle_specs(self, specs):
    assert self.in_model
    self._particle.particle_specs = specs

  @property
  def body_specs(self):
    return self._particle.body_specs if self.in_model else None
  @body_specs.setter
  def body_specs(self, specs):
    assert self.in_model
    self._particle.body_specs = specs

  def __deepcopy__(self, memo):
    gc_copy = deepcopy(self._gridcoord, memo)
    model_p_copy = deepcopy(self._particle, memo)
    return DrawnParticle(gc_copy, self.oval_id, model_p_copy)