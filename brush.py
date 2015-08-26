class Brush(object):
  particle_specs = None
  body_specs = None
  def __init__(self, particle_specs = None, body_specs = None):
    self.particle_specs = particle_specs
    self.body_specs = body_specs

  class ParticleSpecs(object):
    name = None
    color = None
    def __init__(self, name, color):
      self.name = name
      self.color = color
  class BodySpecs(object):
    idx = None
    color = None
    def __init__(self, idx, color):
      self.idx = idx
      self.color = color
