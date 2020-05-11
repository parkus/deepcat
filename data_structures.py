import json
from genericpath import exists
from glob import glob
from os import remove, mkdir
from os.path import join as pathjoin
from astropy.table import Table, MaskedColumn
from math import nan
import warnings

from . import choosers

warn = warnings.warn

def make_column(name, values, dtype='guess'):
    good = list(filter(None, values))

    if dtype == 'guess':
        col = MaskedColumn(good)
        if 'U' in str(col.dtype):
            dtype = 'object'
        else:
            dtype = str(col.dtype)

    mask = [x is None for x in values]
    dtype = dtype.lower()
    if 'i' in dtype or 'f' in dtype:
        nullval = nan
    elif 'a' in dtype or 'u' in dtype:
        nullval = ''
    elif 'o' in dtype:
        nullval = None
    else:
        raise NotImplementedError('Uh oh.')
    values = [nullval if v is None else v for v in values]
    return MaskedColumn(values, name=name, mask=mask, dtype=dtype)


class Extensible(object):
    def __init__(self, **kws):
        for key, val in kws.items():
            self.__setattr__(key, val)


class Catalog(object):
    def __init__(self, objects=None, chooser='default'):
        self.objects = objects
        self.chooser = chooser
        if type(chooser) is str:
            self.chooser = choosers.__dict__[chooser]

    @classmethod
    def from_catalog(cls, catalog):
        """This is just to make upgrading catalogs to new versions easier as I debug the code."""
        objects = [Object.from_object(obj) for obj in catalog.objects]
        return Catalog(objects, catalog._chooser)

    @property
    def chooser(self):
        return self._chooser

    @chooser.setter
    def chooser(self, value):
        if type(value) is str:
            try:
                self._chooser = choosers.__dict__[value]
            except KeyError:
                raise KeyError('{} is not a chooser defined in the choosers module.'.format(value))
        elif hasattr(value, '__call__'):
            self._chooser = value
        else:
            raise ValueError('Chooser can only be set with a string matching the name of a function in the choosers module or a user-defined function.')


    def choose(self, property, object='all', quantity='value', default=None):
        if object == 'all':
            values = [self.choose(property, o, quantity, default) for o in self.object_names]
            return values
        else:
            msmts = self[object][property].measurements
            chosen_msmt = self.chooser(msmts)
            if chosen_msmt == []:
                return default
            value = getattr(chosen_msmt, quantity)
            return value

    @classmethod
    def _get_obj_paths(self, dir):
        search_str = pathjoin(dir, '*.object')
        paths = glob(search_str)
        return sorted(paths)

    def write(self, path, overwrite=False):
        if exists(path):
            if overwrite:
                obj_paths = self._get_obj_paths(path)
                for opath in obj_paths:
                    remove(opath)
                print("Updating object files in specified path. You might want to do a Git commit or equivalent in the directory you specified.")
            else:
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
    def empty_catalog(cls, object_names, property_names):
        objects = []
        for name in object_names:
            obj = Object(name)
            props = [Property(n) for n in property_names]
            obj.properties = props
            objects.append(obj)
        return Catalog(objects)

    def add_measurements(self, object_names, property_name, values, errors=None, references=None, limits=None, qualities=None):
        errors = [None]*len(self) if errors is None else errors
        if references is None:
            references = [None]*len(self)
        if type(references) is str:
            references = [references]*len(self)
        limits = ['=']*len(self) if limits is None else limits
        qualities = [None]*len(self) if qualities is None else qualities
        args = zip(object_names, values, errors, references, limits, qualities)
        for name, v, e, r, l, q in args:
            self[name].add_measurement(property_name, v, e, r, l, q)

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
    def objects(self):
        return list(self._objects.values())

    def add_object(self, object):
        try:
            self._objects[object.name] = object
        except KeyError:
            raise KeyError('No {} object in the catalog.'.format(object))

    def __add__(self, other):
        if isinstance(other, Object):
            self._objects[other.name] = other
        elif isinstance(other, Catalog):
            objects = {**self._objects, **other._objects}
            return Catalog(objects, chooser=self.chooser)

    @objects.setter
    def objects(self, value):
        if value is None:
            self._objects = {}
        elif type(value) in (list, tuple):
            d = {}
            for obj in value:
                d[obj.name] = obj
            self._objects = d
        elif type(value) is dict:
            self._objects = value
        else:
            raise ValueError('"objects" attribute can only be set with None, a list or tuple, or a dictionary and will be made into a dictionary.')

    @property
    def property_names(self):
        propset = set()
        for obj in self._objects.values():
            propset = propset | set(obj.property_names)
        return list(propset)

    @property
    def object_names(self):
        return list(self._objects.keys())

    def __getitem__(self, item):
        return self._objects[item]

    def view(self, name):
        if name not in self.property_names:
            raise KeyError('No {} property for any object in the catalog.'.format(name))
        else:
            props = []
            for oname, obj in self._objects.items():
                rep = '{}: '.format(oname)
                if name in obj:
                    prop = obj[name]
                    rep += ', '.join(map(str, prop.measurements))
                else:
                    rep += 'No {} property defined.'.format(name)
                props.append(rep)
        print(name)
        print('='*len(name))
        [print(p) for p in props]

    def __len__(self):
        return len(self._objects)

    def __delitem__(self, key):
        del self._objects[key]

    def __contains__(self, item):
        return item in self._objects

    def get(self, object_name, property, choose=True):
        obj = self[object_name]
        if property not in obj:
            return None
        else:
            prop = obj[property]
            if choose:
                if len(prop.measurements) == 0:
                    return None
                msmt = self.chooser(prop.measurements)
                return msmt
            else:
                return prop.measurements

    def as_tables(self):
        # values, limits, poserr, negerr, refs
        tables = {'value' : {},
                  'limit' : {},
                  'errpos' : {},
                  'errneg' : {},
                  'quality' : {},
                  'ref' : {}}
        props = self.property_names

        # add names of properties as keys (eventually to be column names) in each table dictionary
        if 'object' in self.property_names:
            warn('Apparently the objects have a property called object. However, the object column in the tables will give the names of the objects, not their "object.object" property.')
        for tbl in tables.values():
            index = MaskedColumn(self.object_names, name='object')
            tbl['object'] = index
            for prop in props:
                tbl[prop] = []

        # construct lists that will become tables
        arbitrary_picks = []
        for obj in self.objects:
            # for each property, add the chosen measurement, if any, to the table
            for prop in props:
                if prop in obj:
                    msmts = obj[prop].measurements
                    if len(msmts) > 0:
                        with warnings.catch_warnings(record=True) as w:
                            warnings.simplefilter('always')
                            msmt = self.chooser(msmts)
                            if len(w) > 0:
                                arbitrary_picks.append([obj.name, prop])
                        tables['value'][prop].append(msmt.value)
                        tables['limit'][prop].append(msmt.limit)
                        tables['errpos'][prop].append(msmt.errpos)
                        tables['errneg'][prop].append(msmt.errneg)
                        tables['quality'][prop].append(msmt.quality)
                        tables['ref'][prop].append(msmt.reference)
                        continue
                for key in tables.keys():
                    tables[key][prop].append(None)
        if len(arbitrary_picks) > 0:
            msg = ('\nCould not select a "best" measurement according to the '
                   'catalog\'s chooser for the following:')
            for ap in arbitrary_picks:
                msg += ('\n    {}: {}'.format(*ap))
            warn(msg)

        # format columns for use in table: set Nones to masked values and infer data types
        for prop in props:
            values = tables['value'][prop]
            tables['value'][prop] = make_column(prop, values)

            values = tables['limit'][prop]
            tables['limit'][prop] = make_column(prop, values, 'a1')

            values = tables['errpos'][prop]
            tables['errpos'][prop] = make_column(prop, values, 'float')

            values = tables['errneg'][prop]
            tables['errneg'][prop] = make_column(prop, values, 'float')

            values = tables['quality'][prop]
            tables['quality'][prop] = make_column(prop, values, 'f2')

            values = tables['ref'][prop]
            tables['ref'][prop] = make_column(prop, values, 'object')

        for key, cols in tables.items():
            tables[key] = Table(cols, masked=True)

        for tbl in tables.values():
            tbl.add_index('object')

        return tables


class Object(object):
    def __init__(self, name, properties=None):
        self.name = name
        if properties is None:
            self.properties = {}
        else:
            self.properties = properties

    def to_json(self):
        d = self.__dict__.copy()
        props = d.pop('_properties')

        # for each entry that is actually a list of objects, get the dictionary form of each
        jprops = [prop.json_ready() for prop in props.values()]
        d['properties'] = jprops

        # now serialize the whole thing
        return json.dumps(d, indent=4)

    @classmethod
    def from_object(cls, object):
        props = [Property.from_property(p) for p in object.properties]
        return Object(object.name, props)

    @classmethod
    def from_json(cls, s):
        d = json.loads(s)

        dprops = d['properties']
        props = [Property.from_dict(dp) for dp in dprops]

        return Object(d['name'], props)

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
        return list(self._properties.values())

    def add_measurement(self, property_name, value, error=None, reference=None, limit='=', quality=None, **kws):
        if property_name not in self:
            self._properties[property_name] = Property(property_name)
        self[property_name].add_measurement(value, error, reference, limit, quality, **kws)

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
        return self._properties.keys()

    def get_property(self, name):
        try:
            return self._properties[name]
        except KeyError:
            raise KeyError('Object does not have a {} property.'.format(name))

    def __add__(self, other):
        if isinstance(other, Property):
            self._properties[other.name] = other
        elif isinstance(other, Object):
            props = {**self._properties, **other._properties}
            return Object(props)

    def __contains__(self, item):
        return item in self._properties

    def __getitem__(self, item):
        return self.get_property(item)

    def __setitem__(self, key, value):
        if not isinstance(value, Property):
            raise ValueError('Can only set a property with a Property object.')
        self._properties[key] = value

    def __delitem__(self, key):
        del self._properties[key]

    def __len__(self):
        return len(self._properties)


class Property(Extensible):
    def __init__(self, name, measurements=None, **kws):
        super(Property, self).__init__(**kws)
        self.name = name
        if measurements is None:
            self.measurements = []
        else:
            self.measurements = measurements

    @classmethod
    def from_property(cls, property):
        msmts = [Measurement.from_measurement(m) for m in property.measurements]
        return Property(property.name, msmts)

    def json_ready(self):
        d = self.__dict__.copy()

        # for each entry that is actually a list of objects, get the dictionary representation of each
        msmts = d.pop('measurements')
        jmsmts = [m.__dict__ for m in msmts]
        d['measurements'] = jmsmts

        # now serialize the whole thing
        return d

    @classmethod
    def from_dict(cls, d):
        msmts = []
        for msmt in d['measurements']:
            for key in ['_value', '_error', '_reference', '_limit', '_quality']:
                if key in msmt:
                    msmt[key[1:]] = msmt.pop(key)
            msmts.append(Measurement(**msmt))
        d['measurements'] = msmts

        return Property(**d)

    def __repr__(self):
        rep = '{}: '.format(self.name)
        if len(self.measurements) > 0:
            msmt_strings = list(map(str, self.measurements))
            rep += ', '.join(msmt_strings)
        else:
            rep += 'no measurements'
        return rep

    def __len__(self):
        return len(self.measurements)

    def add_measurement(self, value, error=None, reference=None, limit='=', quality=None, **kws):
        msmt = Measurement(value, error, reference, limit, quality, **kws)
        self.measurements.append(msmt)


class Measurement(Extensible):
    default_attributes = {'value', 'error', 'reference', 'limit', 'quality'}

    def __init__(self, value, error=None, reference=None, limit='=', quality=None, **kws):
        super(Measurement, self).__init__(**kws)
        self.value = value
        self.error = error
        self.reference = reference
        self.limit = limit
        self.quality = quality

    @classmethod
    def from_measurement(cls, measurement):
        m = measurement
        ckeys = m.custom_attributes
        cdict = {k: getattr(m, k) for k in ckeys}
        return Measurement(m.value, m.error, m.reference, m.limit, m.quality,
                           **cdict)

    @property
    def custom_attributes(self):
        return set(self.__dict__.keys()) - self.default_attributes

    @property
    def simple_error(self):
        if self._error is None:
            return None
        e1, e2 = self._error
        return (abs(e1) + abs(e2))/2.

    @property
    def error(self):
        return self._error

    @property
    def errneg(self):
        if self._error is None:
            return None
        else:
            return self._error[1]

    @property
    def errpos(self):
        if self._error is None:
            return None
        else:
            return self._error[0]

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