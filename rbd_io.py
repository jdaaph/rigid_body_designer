import random, math
import xml.parsers.expat

from brush import Brush
from model import Model, Particle

def random_position(model, box_width, box_height):
  angle = random.uniform(0, 2*math.pi)
  offset_x = random.uniform(0, box_width)
  offset_y = random.uniform(0, box_height)

  return transform_particle_positions(model, offset_x, offset_y, angle)

def transform_particle_positions(model, offset_x, offset_y, angle = 0):
  diameter = 1

  particles = model.particles
  gridcoords = [p.gridcoord for p in particles]
  grid = model.grid
  bbox = grid.gridcoord_to_pixel_bbox(grid.calc_bbox(gridcoords), diameter)
  if bbox == None:  return None

  particle_pixel_coords = [grid.gridcoord_to_pixel(gc, diameter) for gc in gridcoords]
  particle_pos = [(x - bbox[0], y - bbox[1]) for x,y in particle_pixel_coords]

  cosine = math.cos(angle)
  sine = math.sin(angle)
  transformed_pos = [(x*cosine + y*sine + offset_x, -x*sine + y*cosine + offset_y) for x,y in particle_pos]

  #print "Angle =", angle
  #print "Offset = ({0}, {1})".format(offset_x, offset_y)
  #print "Grid points:", particle_grid_coords
  #print "Pixels:", particle_pos
  #print "Transformed:", transformed_pos

  return transformed_pos


def calc_model_lattice_positions(models, copies):
  diameter = 1

  spacing_x = 1.3
  spacing_y = 1.3

  tot_area = 0
  model_sizes = dict()
  max_width = 0
  for model, num_copies in zip(models, copies):
    grid = model.grid
    bbox = grid.gridcoord_to_pixel_bbox(grid.calc_bbox(list(model.points_iterator())), diameter)
    model_width = bbox[2] - bbox[0]
    model_height = bbox[3] - bbox[1]
    model_sizes[model] = (model_width, model_height)
    tot_area += num_copies * (model_width * spacing_x) * (model_height * spacing_y)
    max_width = max(max_width, model_width)

  width = max(max_width, math.ceil(math.sqrt(tot_area))) # The height may be longer because of wasted space


  lattice_positions = []
  x = 0
  y = 0
  height = 0
  for model, num_copies in zip(models, copies):
    print "msize:", model_sizes[model]
    model_w = model_sizes[model][0]
    model_h = model_sizes[model][1]
    for i in range(num_copies):
      if x + model_w > width:
        x = 0
        y = height
      lattice_positions.append((x,y))
      height = max(height, y + math.ceil(spacing_y*model_h))
      x += math.ceil(spacing_x*model_w)

  lattice_positions = [(x - width/2.0, y - height/2.0) for x,y in lattice_positions]

  return ((width, height), lattice_positions)


def export_xml(path, models, copies):
  tot_particles = sum([num_copies * len(model.particles) for model, num_copies in zip(models, copies)])
  print "Exporting to", path
  print "Total number of particles:", tot_particles

  size, lattice_positions = calc_model_lattice_positions(models, copies)
  print "Box dimensions:", size
  lattice_positions = iter(lattice_positions)

  out = open(path, 'w')
  out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  out.write('<hoomd_xml version="1.5">\n')
  out.write('<configuration time_step="0" dimensions="2" vizsigma="1.5">\n')
  out.write('<box lx="{0}" ly="{1}" lz="1" xy="0" xz="0" yz="0"/>\n'.format(size[0], size[1]))
  
  out.write('<position num="{0}">\n'.format(tot_particles))
  for model, num_copies in zip(models, copies):
    for i in range(num_copies):
      offset_x, offset_y = lattice_positions.next()
      pos = transform_particle_positions(model, offset_x, offset_y)
      for x,y in pos:
        out.write('{0} {1} 0.0\n'.format(x, y))
  out.write('</position>\n')
  
  out.write('<body num="{0}">\n'.format(tot_particles))
  idx_offset = 0
  for model, num_copies in zip(models, copies):
    num_bodies = len(set([p.body_specs.idx for p in model.particles]))
    print "Number of rigid bodies in model ({0} copies):".format(num_copies), num_bodies
    for i in range(num_copies):
      for p in model.particles:
        out.write('{0}\n'.format(p.body_specs.idx + idx_offset))
      idx_offset = idx_offset + num_bodies
  out.write('</body>\n')

  out.write('<type num="{0}">\n'.format(tot_particles))
  for model, num_copies in zip(models, copies):
    for i in range(num_copies):
      for p in model.particles:
        out.write(p.particle_specs.name + '\n')
  out.write('</type>\n')

  out.write('<diameter num="{0}">\n'.format(tot_particles))
  out.write('1.0\n' * tot_particles)
  out.write('</diameter>\n')

  out.write('</configuration>\n')
  out.write('</hoomd_xml>\n')

  out.close()

def export_rbd(path, models, particle_specs, body_specs):
  out = open(path, 'w')

  out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  out.write('<rbd num_models="{0}" num_particle_specs="{1}" num_body_specs="{2}">\n'.format(len(models), len(particle_specs), len(body_specs)))
  for i, p_specs in enumerate(particle_specs):
    out.write('<particle_specs index="{0}" name="{1}" color="{2}" />\n'.format(i, p_specs.name, p_specs.color))
  for i, b_specs in enumerate(body_specs):
    out.write('<body_specs index="{0}" color="{1}" />\n'.format(i, b_specs.color))
  for i, model in enumerate(models):
    particles = model.particles
    grid = model.grid
    grid_type = grid.grid_type
    box = grid.calc_bbox([p.gridcoord for p in particles])
    out.write('<model index="{0}" grid_type="{1}" bbox="{2}">\n'.format(i, grid_type, box))
    for particle in particles:
      gridcoord = particle.gridcoord
      p_specs = particle.particle_specs.name
      b_specs = particle.body_specs.idx
      out.write('<particle grid_coord="{0}" particle_specs="{1}" body_specs="{2}" />\n'.format(gridcoord, p_specs, b_specs))
    out.write('</model>\n')
  out.write('</rbd>\n')

def import_rbd(path, rbd):
  model_data = []
  model_particles = []
  particle_specs = []
  body_specs = []
  particle_specs_dict = dict()
  body_specs_dict = dict()
  def process_node_start(name, attr,
      model_data = model_data, model_particles = model_particles,
      particle_specs = particle_specs, particle_specs_dict = particle_specs_dict,
      body_specs = body_specs, body_specs_dict = body_specs_dict):
    if name == 'rbd':
      return
    elif name == 'particle_specs':
      specs = Brush.ParticleSpecs(name = attr['name'], color = attr['color'])
      particle_specs.append(specs)
      particle_specs_dict[attr['name']] = specs
    elif name == 'body_specs':
      specs = Brush.BodySpecs(idx = int(attr['index']), color = attr['color'])
      body_specs.append(specs)
      body_specs_dict[attr['index']] = specs
    elif name == 'model':
      model_data.append(int(attr['grid_type']))
      model_particles.append([])
    elif name == 'particle':
      gridcoord = eval(attr['grid_coord'])
      particle_specs = particle_specs_dict[attr['particle_specs']]
      body_specs = body_specs_dict[attr['body_specs']]
      model_particles[-1].append(Particle(gridcoord = gridcoord, particle_specs = particle_specs, body_specs = body_specs))

  design_box = rbd.design_box
  tool_box = rbd.tool_box

  p = xml.parsers.expat.ParserCreate()
  p.StartElementHandler = process_node_start
  p.ParseFile(open(path, 'r'))

  tool_box.set_particle_specs(particle_specs)
  tool_box.set_body_specs(body_specs)

  models = []
  for data, particles in zip(model_data, model_particles):  
    m = Model(grid_type = data)
    m.particles = particles
    models.append(m)
  tool_box.set_models(models)
