Deepcat is a data structure for storing measurements of the properties of objects. Catalogs of stars are what I had in mind. The problem is often there are multiple measurements of the same thing by different groups. Not only that, but these measurements include a variety of metadata, such as uncertainties. Some of them are limits. I wanted to track all this and the references for each.

Deepcat is, like the name suggests, intended to be deep. Consequently, I didn't optimize it for speed. I intended it for catalogs of up to a few hundred, maybe a few thousand objects. After that, I suspect it will scale poorly because it does not use arrays. The tradeoff is that it is flexible and extensible. For example, you could add an attribute to a measurement that gives the date it was made or add a detailed posterior distribution. Just note that these must be json serializable if you want to be able to save the data without modifying the Deepcat code.

Deepcat is intended to be used with Git or similar for version tracking, collaborating, and backup. It will save its output into a directory as a .json file for each object in the catalog. Users should initialize that directory as a Git (or whatever) repository and commit changes as they see fit.

If anyone actually wants to use this code, let me know and that might prod me to better document it :)

Quick Start
-----------
```
# let's make initialize a few stars that have measurements of their radii
import deepcat as dc
proxcen = dc.Object('Proxima Centauri')
vega = dc.Object('Vega')
proxcen.add_measurement('radius', value=0.3, error=0.1, reference='thing one', quality=5)
proxcen.add_measurement('radius', value=0.5, error=0.2, reference='thing two', quality=2)
# anything except the name of the thing being measured and its value is optional
# for example, the quality attribute is just something I added with the thought
# that I might use it to flag measurements that maybe have a great precision
# but should not be trusted

vega.add_measurement('radius', value=0.6, limit='>', reference='thing three')
# this is a lower limit

vega.add_measurement('radius', value=0.8, error=0.05, reference='cat in a hat')

# each object will now have a 'radius' property, which is its own Python object,
# and each Property object contains a set of Measurement objects. You can
# access them like a dictionary
radius = vega['radius']
radius.measurements
# prints:[>0.6 (thing three), 0.8 +0.05/-0.05 (cat in a hat)]

# now lets pile these objects into a catalog
cat = dc.Catalog((proxcen, vega))

# if I want to see the radius measurements of all the objects in the catalog
# I can just do
cat.view('radius')
# which prints
# radius
# ======
# Proxima Centauri: 0.3 +0.1/-0.1 (thing one), 0.5 +0.2/-0.2 (thing two)
# Vega: >0.6 (thing three), 0.8 +0.05/-0.05 (cat in a hat)

# I can also access the objects in the catalog in dictionary style
proxcen = cat['Proxima Centauri']
# Two important things to note here:
# First, the name I gave the object
# originally becomes it's key. So, e.g., cat['proxcen'] wouldn't work unless I
# set proxcen.name = 'proxcen' before I made the catalog.
# Second, this returns the actual object, not a copy. Changes I make to the
# object will show up in the catalog.

# I can have the catalog give me tables of the values, errors, etc. of
# every Property of every Object it contains, like this
tbls = cat.as_tables()
tbls['value'] #prints
# <Table masked=True length=2>
#      object       radius
#      str16       float64
# ---------------- -------
# Proxima Centauri     0.3
#             Vega     0.8

# you might be wondering why those values were chosen, given that there were
# multiple measurements of each. Each catalog has an associated "chooser", which
# is a function that, if given a list of measurements, will decide which is best
# and return it. The point is that you can make your own choosers that use their
# own rules. The functions in the "choosers" module are for this. Note that only
# the "default" chooser will work for this at the moment. The others in that module all
# return lists instead of single measurements. The default chooser first looks
# for measurements that aren't upper limits, then selects those of the highest
# quality, then those of the best precision (smallest error/value). If
# multiple measurements have the same quality and precision, then it arbitrarily
# picks one and issues a warning.

# now the most important part of this catalog is that you can save it to a
# directory
cat.write('my_catalog')
# the code will then remind you that you should probably initialize version
# control int he directly it created so you can track updates to your catalog.
# you must handle this tracking *on your own*, deepcat does not do it for you.

# in the directory deepcat creates, there will be a separate ".object" file for
# each object in the catalog. These are json files (so, kinda human readable)
# with the measurements for each property of that object. If you make updates
# and want to save to the same directory, you will have to tell deepcat that it
# is okay to overwrite.
cat.write('my_catalog', overwrite=True)

 # and then to read this catalog back in, just do
 cat = dc.Catalog.read('my_catalog')

 # That's it for now, folks! Any more than that and you will have to dig around
 # in the methods themselves and experiment to see how things work.
