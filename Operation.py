import Tkinter as tk
from copy import deepcopy

class Operation(object):
  model = None
  cache = {}
  _copy = False
  _name = None
  # var holds the information to be displayed on the GUI
  var_hint = None
  var_cache = None
  operation_box = None

  # cache field shows what information must be passed into the operation to make it work
  _cache_field_needed = []
  operate_func = None
  def __init__(self, model=model, cache={}, cache_field=[], operation_box=None):
    self.model = model
    self.cache = cache
    self._cache_field_needed = cache_field
    # self._copy=True means that the selected particles will still be there after operation
    self._copy = False
    operate_func = None

    # settings for connecting GUI operation_box
    self.operation_box = operation_box
    operation_box.current_operation = self
    self.var_hint = operation_box.var_hint
    self.var_cache = operation_box.var_cache

  def cancel(self, error_msg=None, completed=False):
    ''' cancel this operation and show the message if applicable, completed=True means this operation is successfully run'''
    if error_msg:
      self.var_hint.set("Operation Canceled:")
      self.var_cache.set(error_msg)
    elif completed:
      self.var_hint.set("Operation Complete")
      self.var_cache.set("")
    else:
      self.var_hint.set("Operation Canceled")
      self.var_cache.set("")

    self.model.current_operation = None
    self.model = None
    self.cache = {}

  def fill_cache(self, incoming):
    '''called by enter_bind in Model.py, used to fill the cache with key=next-item-in-fieldneeded , and value=argument'''
    if self._cache_field_needed:
      self.cache[self._cache_field_needed.pop()] = incoming
      self.report_status()
    else:
      self.cancel("cache does not need this, I quit!@!")
  
  def paste(self, ref_point):
    # check all needed cache_fields have been collected
    if self._cache_field_needed:
      self.cancel("Sorry. %s is missing for this task" % self._cache_field_needed.pop())

    self.cache['selected_after_op'] = []

    # iter is to solve the case that bp and rp are the same, then pop will block the assignment of rp
    bp = next(iter(self.cache['base_point']))
    rp = ref_point.pop()
    bp_x, bp_y = bp.grid_coord[0], bp.grid_coord[1]
    rp_x, rp_y = rp.grid_coord[0], rp.grid_coord[1]
    delta_x, delta_y = rp.grid_coord[0]-bp_x, rp.grid_coord[1]-bp_y

    print "bp:" + str(bp.grid_coord)
    print "rp:" + str(rp.grid_coord)

    for par in self.cache['selected']:
      new_par = par.copy()
      new_par.particle_specs = par.particle_specs
      # new_par = par
      self.operate_func(new_par, bp_x, bp_y)
      new_par.grid_coord = (rp_x+ new_par.grid_coord[0], rp_y + new_par.grid_coord[1])
      self.cache['selected_after_op'].append(new_par)

    self.cache['selected_after_op'].extend(self.cache['not_selected'])
    if self._copy:
      self.cache['selected_after_op'].extend(self.cache['selected'])

    self.model.set_particles_paste(self.cache['selected_after_op'])
    self.cancel(completed=True)

  def report_status(self):
    ''' Communicate with operation_box to help you know your next step from GUI'''
    self.var_hint.set(self._name + ' Mode')
    if self._cache_field_needed:
      self.var_cache.set("Choose next your %s, and <Enter>" % self._cache_field_needed[-1])
    else:
      self.var_cache.set("Choose your new reference point and <LeftCommand+V>")

  # below are specific operation functions called by paste
  def operate_rotate_ccw(self, par, x0, y0):
    # x0, y0 are the x/y grid_coord for basepoint(bp)
    x,y = par.grid_coord[0] , par.grid_coord[1]
    par.grid_coord = (y-y0, -(x-x0))

  def operate_copy(self, par, x0, y0):
    x,y = par.grid_coord[0] , par.grid_coord[1]
    par.grid_coord = (x-x0, y-y0)

  def operate_group_set(self, par, specs):
    if 'particle_specs' in specs:
      par.particle_specs = specs['particle_specs']
    if 'body_specs' in specs:
      par.body_specs = specs['body_specs']

 
class Rotate_ccw(Operation):
  def __init__(self, model, cache, operation_box): 
    super(Rotate_ccw, self).__init__(model=model , cache=cache, cache_field=['base_point'], operation_box=operation_box)
    self.operate_func = self.operate_rotate_ccw
    self._copy = False
    self._name = "Rotation(CCW)"
    self.report_status()


class Move(Operation):
  def __init__(self, model , cache, operation_box): 
    super(Copy, self).__init__(model=model , cache=cache, cache_field=['base_point'], operation_box=operation_box)
    self.operate_func = self.operate_copy
    self._copy = False
    self._name = "Move"
    self.report_status()


class Copy(Operation):
  def __init__(self, model , cache, operation_box): 
    super(Copy, self).__init__(model=model , cache=cache, cache_field=['base_point'], operation_box=operation_box)
    self.operate_func = self.operate_copy
    self._copy = True
    self._name = "Copy"
    self.report_status()


class Group_Set(Operation):
  ''' Use this to alter all the selected particles one particular attribute (body,type, etc)'''
  def __init__(self, model , cache, operation_box): 
    super(Group_Set, self).__init__(model=model , cache=cache, cache_field=['new_brush'], operation_box=operation_box)
    self.operate_func = self.operate_group_set
    self._copy = False
    self._name = "Group Setup"
    self.report_status()

  def report_status(self):
    '''overide base method to report status in GUI operation_box'''
    self.var_hint.set(self._name)
    self.var_cache.set("Change the body or particle type")

  def _get_brush_change(self):
    old = self.cache['old_brush']
    new = self.cache['new_brush']
    specs = {}
    if not old.particle_specs == new.particle_specs:
      specs['particle_specs'] = new.particle_specs
    if not old.body_specs == new.body_specs:
      specs['body_specs'] = new.body_specs
    return specs

  def paste(self):
    ''' This overides the BASE paste function to provide change directly to selected particles while not making copies'''

    # check all needed cache_fields have been collected
    if self._cache_field_needed:
      print "Sorry. %s is missing for this task" % self._cache_field_needed.pop()
      self.cancel()    
    specs = self._get_brush_change()

    self.cache['selected_after_op'] = []

    for par in self.cache['selected']:
      new_par = par.copy()
      self.operate_func(new_par, specs)
      self.cache['selected_after_op'].append(new_par)
    
    self.cache['selected_after_op'].extend(self.cache['not_selected'])
    if self._copy:
      self.cache['selected_after_op'].extend(self.cache['selected'])

    self.model.set_particles_paste(self.cache['selected_after_op'])
    self.cancel(completed=True)





