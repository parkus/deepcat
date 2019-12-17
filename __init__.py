import json


#  to handle writing and reading objects that contain lists of other objects. Basically, keeps boilerplate to_json and from_json code"""
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
    def __init__(self, name, objects=None):
        self.name = name
        if objects is None:
            self.objects = []
        else:
            self.objects = objects
        self.references = {}

    def write(self):
        pass

    @classmethod
    def read(cls):
        pass

    def as_tables(self, choose='quality,precision'):
        pass


class Object(object):
    def __init__(self, name, properties=None):
        self.name = name
        if properties is None:
            self.properties = []
        else:
            self.properties = properties

    def to_json(self):
        return pack_json(self, ['properties'])

    @classmethod
    def from_json(cls, s):
        d = unpack_json(s, ['properties'], [Property])
        return Property(**d)

    def __repr__(self):
        pass


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
        pass


class Measurement(Extensible):
    def __init__(self, value, error=None, reference=None, quality=None, **kws):
        super(Measurement, self).__init__(**kws)
        self.value = value
        self.error = error
        self.reference = reference
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
        if hasattr(value, '__len__'):
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
        custom_attrs = attrs - {'value', '_error', 'reference', '_quality'}
        obj = cls(d['value'], d['_error'], d['reference'], d['_quality'])
        for key in custom_attrs:
            obj.__setattr__(key, d[key])
        return obj

    def __repr__(self):
        return ('{:.3g} +{:.3g}/{:.3g} ({})'
                ''.format(self.value, self._error[0], self._error[1],
                          self.reference))