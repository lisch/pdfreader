import logging

from .exceptions import ParserException
from .registry import Registry
from .parser import RegistryPDFParser
from .types import null, IndirectObject, Stream, Array, Dictionary, IndirectReference, ATOMIC_TYPES

is_atomic = lambda obj: isinstance(obj, (ATOMIC_TYPES))


class PDFDocument(object):
    """ PDF document structure (how basic object types are used to represent PDF components:
        pages, fonts, annotations, images etc.) """

    def __init__(self, fobj):
        """ fobj - file-like object

import logging
#logging.basicConfig(filename='pdf.log', filemode='w')
logging.getLogger().setLevel("DEBUG")

from pdfreader import PDFDocument
#fd = open('data/tyler-or-DocumentFragment.pdf','rb')
#fd = open('data/fw8ben.pdf','rb')
#fd = open('data/leesoil-cases-2.pdf','rb')
#fd = open('data/ohcrash-02-0005-02-multiunit.pdf','rb')
#fd = open('data/ohcrash-scanned-case-converted-image.pdf','rb')
#fd = open('data/seattlemuni-cr-charges-brackets','rb')
fd = open('data/PDF32000_2008.pdf','rb')
doc = PDFDocument(fd)


        """

        self.registry = Registry()
        self.parser = RegistryPDFParser(fobj, self.registry)

        self.header = self.parser.pdf_header()
        self.trailer = self.parser.pdf_trailer()

        # save initial state for brute-force objects lookup
        self.parser.reset(self.header.offset)
        self.brute_force_state = self.parser.get_state()

        self.root = self.obj_by_ref(self.trailer.root)

    def build(self, obj, visited=None):
        """ replace all object references with objects
            leave loops as is
            works quite long
        """
        logging.debug("Buliding {}".format(obj))
        if visited is None:
            visited = []

        on_return = None
        if isinstance(obj, IndirectReference):
            if obj not in visited:
                visited.append(obj)
                on_return = visited.pop
                obj = self.obj_by_ref(obj)

        # resolve subsequent references for Arrays, Dictionaries and Streams
        if isinstance(obj, Array):
            obj = [(self.build(o, visited) if not is_atomic(o) else o) for o in obj]
        elif isinstance(obj, Dictionary):
            obj = {k: (self.build(o, visited) if not is_atomic(o) else o) for k, o in obj.items()}
        elif isinstance(obj, Stream):
            obj.dictionary = {k: (self.build(o, visited) if not is_atomic(o) else o)
                              for k, o in obj.dictionary.items()}
        elif isinstance(obj, IndirectObject):
            # normally this shouldn't happen, but ponentially we can build it
            logging.warning("Attempt to build an indirect object. Possibly a bug.")
            obj = self.build(obj.val, visited)

        if on_return:
            on_return()
        return obj

    def locate_object(self, num, gen):
        """
        Object lookup order:
        1. Known objects in registry
        2. XRefs - try to find and load
        3. Brute-force reading objects one by one from the file start
        """
        # Locate by xref
        for xref in self.trailer.xrefs:
            # try to find in-use object
            xre = xref.in_use.get(num)
            if xre.generation == gen:
                try:
                    self.parser.reset(xre.offset)
                    self.parser.indirect_object()
                except ParserException:
                    pass
                if self.registry.is_registered(num, gen):
                    break
            # Try to find a compressed object
            xre = xref.compressed.get(num)
            if xre.generation == gen:
                # Need to locate Object Stream in order to locate a compressed object
                self.locate_object(xre.number, xre.generation)
                if self.registry.is_registered(num, gen):
                    break

        while not self.registry.is_registered(num, gen):
            try:
                _ = self.next_brute_force_object()
            except ParserException:
                # treat not-found objects as nulls
                logging.exception("!!!Failed to locate {} {}: assuming null".format(num, gen))
                self.registry.register(IndirectObject(num, gen, null))
                break
        obj = self.registry.get(num, gen)
        return obj

    def obj_by_ref(self, objref):
        return self.locate_object(objref.num, objref.gen)

    def next_brute_force_object(self):
        self.parser.set_state(self.brute_force_state)
        self.parser.maybe_spaces_or_comments()
        obj = self.parser.body_element() # can be either indirect object, startxref or trailer
        self.brute_force_state = self.parser.get_state() # save state for the next BF
        return obj
