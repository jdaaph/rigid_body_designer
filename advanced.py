import copy

class Operation(object):
  model = None
  cache = {}
  # cache field shows what information must be passed into the operation to make it work
  _cache_field_needed = []
  operate_func = None
  def __init__(self, model=model, group=(), cache={}, cache_field=[]):
    self.model = model
    self.cache = cache
    self._cache_field_needed = cache_field
    operate_func = None

  def fill_cache(self, incoming):
    '''called by enter_bind in Model.py, used to fill the cache with key=next-item-in-fieldneeded , and value=argument'''
    if self._cache_field_needed:
      self.cache[self._cache_field_needed.pop()] = incoming
      print "cache filled"
    else:
      self.model.current_operation = None
      print "cache does not need this, I quit!@!"

  def paste(self, ref_point):
    # check all needed cache_fields have been collected
    print "got paste cmd"

    if self._cache_field_needed:
      print "Sorry. %s is missing for this task" % self._cache_field_needed.pop()

    # Note that ref_point got passed in as a list
    self.cache['group_after_op'] = []
    rp = ref_point.pop()
    bp = self.cache['base_point'].pop()
    bp_x, bp_y = bp.grid_coord[0], bp.grid_coord[1]
    rp_x, rp_y = rp.grid_coord[0], rp.grid_coord[1]
    delta_x, delta_y = rp.grid_coord[0]-bp_x, rp.grid_coord[1]-bp_y

    print "bp:" + str(bp.grid_coord)
    print "rp:" + str(rp.grid_coord)

    for par in self.cache['group']:
      new_par = copy.deepcopy(par)
      # print new_par.grid_coord
      self.operate_func(new_par, bp_x, bp_y)
      # print new_par.grid_coord

      new_par.grid_coord = (rp_x+ new_par.grid_coord[0], rp_y + new_par.grid_coord[1])
      # print new_par.grid_coord
      # print '-------next point--------'
      self.cache['group_after_op'].append(new_par)


    print [par.grid_coord for par in self.cache['group_after_op']]
    print [par.grid_coord for par in self.cache['not_selected']]

    self.model.set_particles_paste(self.cache['group_after_op'].extend(self.cache['not_selected']))
    self.model.current_operation = None
    self.model = None

  # below are specific operation functions called by paste
  def operate_rotate_ccw(self, par, x0, y0):
    # x0, y0 are the x/y grid_coord for basepoint(bp)
    x,y = par.grid_coord[0] , par.grid_coord[1]
    par.grid_coord = (y-y0, -(x-x0))
 


class Rotate_ccw(Operation):
  def __init__(self, model, cache): 
    super(Rotate_ccw, self).__init__(model=model , cache=cache, cache_field=['base_point'])
    self.operate_func = self.operate_rotate_ccw
  # cache = {'group':[the particle-group to be operated], 'base_point':base point particle}


class Copy(Operation):
  def __init__(self, model , cache): 
    super(Rotate_ccw, self).__init__(model=model , cache=cache, cache_field=['base_point'])
    self.operate_func = self.operate_copy
  # cache = {'group':[the particle-group to be operated], 'base_point':base point particle}







