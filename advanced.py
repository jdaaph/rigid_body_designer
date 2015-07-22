import copy

class Operation(object):
  model = None
  cache = {}
  _copy = False

  # cache field shows what information must be passed into the operation to make it work
  _cache_field_needed = []
  operate_func = None
  def __init__(self, model=model, cache={}, cache_field=[]):
    self.model = model
    self.cache = cache
    self._cache_field_needed = cache_field
    # self._copy=True means that the selected particles will still be there after operation
    self._copy = False
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
    if self._cache_field_needed:
      print "Sorry. %s is missing for this task" % self._cache_field_needed.pop()

    # Note that ref_point got passed in as a list
    self.cache['selected_after_op'] = []
    rp = ref_point.pop()
    bp = self.cache['base_point'].pop()
    bp_x, bp_y = bp.grid_coord[0], bp.grid_coord[1]
    rp_x, rp_y = rp.grid_coord[0], rp.grid_coord[1]
    delta_x, delta_y = rp.grid_coord[0]-bp_x, rp.grid_coord[1]-bp_y

    print "bp:" + str(bp.grid_coord)
    print "rp:" + str(rp.grid_coord)

    for par in self.cache['selected']:
      new_par = copy.deepcopy(par)
      self.operate_func(new_par, bp_x, bp_y)
      new_par.grid_coord = (rp_x+ new_par.grid_coord[0], rp_y + new_par.grid_coord[1])
      self.cache['selected_after_op'].append(new_par)

    self.cache['selected_after_op'].extend(self.cache['not_selected'])
    if self._copy:
      self.cache['selected_after_op'].extend(self.cache['selected'])

    self.model.set_particles_paste(self.cache['selected_after_op'])
    self.model.current_operation = None
    self.model = None

  # below are specific operation functions called by paste
  def operate_rotate_ccw(self, par, x0, y0):
    # x0, y0 are the x/y grid_coord for basepoint(bp)
    x,y = par.grid_coord[0] , par.grid_coord[1]
    par.grid_coord = (y-y0, -(x-x0))

  def operate_copy(self, par, x0, y0):
    x,y = par.grid_coord[0] , par.grid_coord[1]
    par.grid_coord = (x-x0, y-y0)

 
class Rotate_ccw(Operation):
  def __init__(self, model, cache): 
    super(Rotate_ccw, self).__init__(model=model , cache=cache, cache_field=['base_point'])
    self.operate_func = self.operate_rotate_ccw
    self._copy = False


class Move(Operation):
  def __init__(self, model , cache): 
    super(Copy, self).__init__(model=model , cache=cache, cache_field=['base_point'])
    self.operate_func = self.operate_copy
    self._copy = False


class Copy(Operation):
  def __init__(self, model , cache): 
    super(Copy, self).__init__(model=model , cache=cache, cache_field=['base_point'])
    self.operate_func = self.operate_copy
    self._copy = True







