import json
from genericpath import exists
from glob import glob
from os import remove, mkdir
from os.path import join as pathjoin

import choosers


def pack_json(self, containers=None):
    d = self.__dict__.copy()

    # for each entry that is actually a list of objects, json serialize each of those objects
    if containers is not None:
        for key in containers:
            objs = d[key]
            jobjs = [obj.to_json() for obj in objs]
            d[key] = jobjs

    # now serialize the whole thing
    return json.dumps(d)


def unpack_json(s, containers=None, classes=None):
    d = json.loads(s)

    if containers is not None:
        for key, ccls in zip(containers, classes):
            jobjs = d[key]
            objs = [ccls.from_json(jobj) for jobj in jobjs]
            d[key] = objs

    return d


class Extensible(object):
    def __init__(self, **kws):
        for key, val in kws.items():
            self.__setattr__(key, val)


class Catalog(object):
    def __init__(self, objects=None, chooser='default'):
        if objects is None:
            self.objects = []
        else:
            self.objects = objects
        self.references = {}
        self.chooser = chooser
        if type(chooser) is str:
            self.chooser = choosers.__dict__(chooser)

    @property
    def chooser(self):
        return self._chooser

    @chooser.setter
    def chooser(self, value):
        if type(value) is str:
            try:
                self.chooser = choosers.__dict__(value)
            raise KeyError('{} is not a chooser defined in the choosers module.'.format(value))
        elif hasattr(value, '__call__'):
            self.chooser = value
        else:
            raise ValueError('Chooser can only be set with a string matching the name of a function in the choosers module or a user-defined function.')

    @classmethod
    def _get_obj_paths(self, dir):
        search_str = pathjoin(dir, '*.object')
        return glob(search_str)

    def write(self, path, overwrite=False):
        if exists(path):
            if overwrite:
                obj_paths = self._get_obj_paths(path)
                for opath in obj_paths:
                    remove(opath)
                print("Updating object files in specified path. You might want to do a Git commit or equivalent in the directory you specified.")
            raise ValueError('Path exists. User overwrite=True ot overwrite.')
        else:
            mkdir(path)
            print("Created a new directory for the catalog at \n{}\nYou might want to initiliaze a version control system in that directory now.".format(path))

        for obj in self.objects:
            obj_filename = '{}.object'.format(obj.name)
            obj_path = pathjoin(path, obj_filename)
            s = obj.to_json()
            with open(obj_path, 'w') as f:
                f.write(s)

    @classmethod
    def read(cls, path):
        obj_paths = cls._get_obj_paths(path)
        objs = []
        for path in obj_paths:
            with open(path) as f:
                s = f.read()
                obj = Object.from_json(s)
                objs.append(obj)
        return Catalog(objects=objs)

    @property
    def property_names(self):
        propset = {}
        for obj in self.objects:
            propset += set(obj.propnames)
        return list(propset)

    @property
    def object_names(self):
        return [obj.name for obj in self.objects]

    def __getattr__(self, item):
        objlist = [obj for obj in self.objects if obj.name == item]
        if len(objlist) == 1:
            return objlist[0]
        else:
            raise AttributeError('{} is not an attribute of the catalog nor an object in the catalog.'.format(item))

    def get(self, object_name, property, choose=True):
        obj = self.__getattr__(object_name)
        prop = obj.__getattr__(property)
        if choose:
            if len(prop.measurements) == 0:
                return None
            msmt = self.chooser(prop.measurements)
            if len(msmts) == 0:
                raise ValueError('Uh oh, somehow no measurements could be chosen as best with the catalogs chooser.')
            elif len(msmts) == 1:
                return msmts[0]
            else:
                raise ValueError('Uh oh, the catalog\'s chooser chose multiple measurements as best.')

    def extract_tables(self):
        # values, limits, poserr, negerr, refs
        tables = {'values' : [],
                  'limits' : [],
                  'poserr' : [],
                  'negerr' : [],
                  'refs' : []}
        props = self.property_names

        # construct lists that will become tables
        for obj in self.objects:

            # add an empty row (just an empty list) for the object to each table
            for key in tables.keys():
                tables[key].append([])

            # for each property, add the chosen measurement, if any, to the table
            for prop in props:
                if prop in obj:
                    msmts = obj[prop].measurements
                    if len(msmts) > 0:
                        msmt = self.chooser(msmts)[0]
                        row.append(msmt.value)


class Object(object):
    def __init__(self, name, properties=None):
        self.name = name
        if properties is None:
            self.properties = {}
        else:
            self.properties = properties

    def to_json(self):
        return pack_json(self, ['properties'])

    @classmethod
    def from_json(cls, s):
        d = unpack_json(s, ['properties'], [Property])
        return Object(**d)

    def __repr__(self):
        rep = self.name
        rep += '\n' + '='*len(self.name)
        if len(self.properties) > 0:
            for prop in self.properties:
                rep += '\n' + str(prop)
        else:
            rep += '\n' + 'no properties'
        rep += '\n'
        return rep

    @property
    def properties(self):
        return self._properties

    @properties.setter
    def properties(self, value):
        if value is None:
            self._properties = {}
        elif type(value) in (list, tuple):
            d = {}
            for prop in value:
                d[prop.name] = prop
            self._properties = d
        elif type(value) is dict:
            self._properties = value
        else:
            raise ValueError('"properties" attribute can only be set with None, a list or tuple, or a dictionary and will be made into a dictionary.')

    @property
    def property_names(self):
        return self.properties.keys()

    def get_property(self, name):
        try:
            self.properties[name]
        except KeyError:
            raise KeyError('Object does not have a {} property.'.format(name))

    def __getattr__(self, item):
        try:
            return self.get_property(item)
        except KeyError:
            raise AttributeError('{} is not an attribute of the object nor a property in the object\'s properties list.'.format(item))

    def __getitem__(self, item):
        return self.get_property(item)

    def __setitem__(self, key, value):
        if not isinstance(value, Property):
            raise ValueError('Can only set a property with a Property object.')
        self.properties[key] = value


class Property(Extensible):
    def __init__(self, name, measurements=None, **kws):
        super(Property, self).__init__(**kws)
        self.name = name
        if measurements is None:
            self.measurements = []
        else:
            self.measurements = measurements

    def to_json(self):
        return pack_json(self, ['measurements'])

    @classmethod
    def from_json(cls, s):
        d = unpack_json(s, ['measurements'], [Measurement])
        return Property(**d)

    def __repr__(self):
        rep = '{}: '.format(self.name)
        if len(self.measurements) > 0:
            msmt_strings = list(map(str, self.measurements))
            rep += ', '.join(msmt_strings)
        else:
            rep += 'no measurements'
        return rep

    def collapsed(self, method='pick'):
        pass


class Measurement(Extensible):
    def __init__(self, value, error=None, reference=None, limit='=', quality=None, **kws):
        super(Measurement, self).__init__(**kws)
        self.value = value
        self.error = error
        self.reference = reference
        self.limit = limit
        self.quality = quality

    @property
    def simple_error(self):
        e1, e2 = self._error
        return (abs(e1) + abs(e2))/2.

    @property
    def error(self):
        return self._error

    @error.setter
    def error(self, value):
        if value is None:
            self._error = None
        elif hasattr(value, '__len__'):
            if len(value) == 1:
                self.error = value[0]
            if len(value) == 2:
                    if value[0]/value[1] >= 0:
                        raise ValueError('If providing an asymmetric error, '
                                         'you must give one positive and one '
                                         'negative number.')
                    if value[0] < 0:
                        self._error = value[1], value[0]
                    else:
                        self._error = tuple(value)
            else:
                raise ValueError('You must give either a single value or an '
                                 'iterable of two values for the error.')
        else:
            self._error = value, -value

    @property
    def limit(self):
        return self._limit

    @limit.setter
    def limit(self, flag):
        if flag not in '<=>':
            raise ValueError('Limit must be one of =, <, or >.')
        else:
            self._limit = flag

    @property
    def quality(self):
        return self._quality

    @quality.setter
    def quality(self, value):
        if value is None:
            self._quality = None
        elif value < 0 or value > 5:
            raise ValueError('Quality must be in the range [0,5].')
        else:
            self._quality = value

    def to_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, s):
        d = json.loads(s)
        attrs = set(d.keys())
        custom_attrs = attrs - {'value', '_error', '_limit' 'reference', '_quality'}
        obj = cls(d['value'], d['_error'], d['reference'], d['_limit'], d['_quality'])
        for key in custom_attrs:
            obj.__setattr__(key, d[key])
        return obj

    def __repr__(self):
        if type(self.value) is str:
            rep = self.value
        else:
            if self.limit in '<>':
                rep = self.limit
            else:
                rep = ''
            rep += '{:.3g}'.format(self.value)
            if self.error is not None:
                rep += ' +{:.3g}/{:.3g}'.format(*self._error)
        if self.reference is None:
            rep += ' (no ref)'
        else:
            rep += ' ({})'.format(self.reference)
        return rep