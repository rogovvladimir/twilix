from twisted.words.xish.domish import Element

from twilix.base.exceptions import ElementParseError, WrongElement

class EmptyStanza(object):   
    """Dummy stanza to send when nothing to send."""
    pass

class EmptyElement(object):
    """Dummy Element."""
    pass

class BreakStanza(object):   
    """Stanza that breaks handling loop."""
    pass

class MyElement(Element):
    """
    Extend class Element from twisted.words.xish.domish.
    Base class for all Elements.
    
    Attributes:
       attributesProps - dictionary of attributes names/fields.
       
       nodesProps - dictionary of node's names/fields.
    
    """
    
    attributesProps = {}
    nodesProps = {}
    
    @classmethod
    def makeFromElement(cls, el):
        """
        Make new element according to class that calls
        this method from element el.
                
        :param el: element to copy
        :type el: Element
        
        :returns:  myel -- copy of element el
        
        """
        myel = cls((el.uri, el.name))
        myel.attributes = el.attributes
        for c in el.children:
            if isinstance(c, (str, unicode)):
                myel.children.append(c)
            else:
                myel.children.append(cls.makeFromElement(c))
        return myel

    @classmethod
    def createFromElement(cls, el, host=None, **kwargs):
        """
        Make class instance of element if it's suits to class.
                
        :returns: class instance with host and kwargs of element
        
        :raises: WrongElement
        
        """
        if isinstance(cls.elementUri, (tuple, list)):
            if el.uri not in cls.elementUri:
                raise WrongElement
        elif el is None:
            raise WrongElement
        else:
            if cls.elementUri is not None and el.uri != cls.elementUri:
                raise WrongElement
        if cls.elementName is not None and el.name != cls.elementName:
            raise WrongElement
        for name, attr in cls.attributesProps.items():
            kwargs[name] = el.attributes.get(attr.xmlattr, None)
        for name, attr in cls.nodesProps.items():
            kwargs[name] = attr.get_from_el(el)
        r = cls(host=host, **kwargs)
        r.children = el.children
        return r

    @classmethod
    def topClass(cls):
        """
        Return top class in class hierarchy.
        
        :returns:  
            cls if class have not parent class
            
            top class of parent class otherwise
            
        """
        parent = getattr(cls, 'parentClass', None)
        if parent:
            return parent.topClass()
        return cls

    def validate(self):
        """Validate all attributes."""
        parent = getattr(self, 'parent', None)
        if parent is not None:
            parent.validate()
        for name, attr in self.__class__.attributesProps.items():
            getattr(self, name, None)
        for name, attr in self.__class__.nodesProps.items():
            getattr(self, name, None)

    def __getattr__(self, name):  #XXX: refactor?
        """Overrides __getattr__ method.
        
        Return valid attribute or not listed node if it's exist.
        
        Return list of valid childrens of node if it's listed.
        
        Return function adder or remover if it's required and node is
        listed.
        
        Call __getattr__ method of super class otherwise.  
               
        """
        need_adder = False
        need_remover = False
        if name.startswith('add'):
            name = name[3:].lower()
            need_adder = True
        elif name.startswith('remove'):
            name = name[6:].lower()
            need_remover = True
        attr = self.attributesProps.get(name, None)
        node = self.nodesProps.get(name, None)
        if attr and not need_adder:
            return self._validate(name, attr, attr.get_from_el(self))
        elif node:
            if need_adder and node.listed:
                def adder(value):
                    if not isinstance(value, (tuple, list)):
                        values = (value,)
                    else:
                        values = value
                    r = False
                    node = self.nodesProps.get(name)
                    old = getattr(self, name, ())
                    for value in values:
                        if node.unique and value in old:
                            continue
                        r = True
                        content = self._validate(name, node, value)
                        if isinstance(content, MyElement):
                            self.addChild(content)
                        else:
                            n = MyElement((None, xmlnode))
                            node.addChild(unicode(content))
                            self.addChild(n)
                    return r
                return adder
            elif need_remover and listed:   #XXX: node.listed?
                def remover(value):
                    if not isinstance(value, (tuple, list)):
                        values = [value,]
                    else:
                        values = list(value)
                    old_values = list(getattr(self, attr, ()))
                    r = False
                    for value in values:
                        while value in old_values:
                            old_values.remove(value)
                            r = True
                    setattr(self, attr, old_values)
                    return r
                return remover

            elif (need_adder or need_remover):
                return
            if node.listed:
                return [self._validate(name, node, v) \
                        for v in node.get_from_el(self)]
            else:
                return self._validate(name, node, node.get_from_el(self))
        elif not name.startswith('clean_'):
            return super(MyElement, self).__getattr__(name)

    def _validate(self, name, attr, value, setter=False):
        """
        Call cleaning function to attributes value according to the
        name and setter. 
        Return clean value.
        
        :param name: name of attribute
        
        :param attr: attribute
        
        :param value: value of attribute
        
        :param setter: using of setter
        
        :returns: value - clean value
        
        :raises: ElementParseError
        
        """
        #import pdb; pdb.set_trace()
        if not setter:
            value = attr.clean(value)
        if setter and hasattr(attr, 'clean_set'):
            value = attr.clean_set(value)
        if not setter:
            nvalidator = getattr(self, 'clean_%s' % name, None)
            if nvalidator is not None:
                value = nvalidator(value)
        if value is None:
            if attr.required:
                raise ElementParseError, u'attr %s is required' % attr
        return value

    def __setattr__(self, name, value):
        """
        Overrides __setattr__ method.
        
        Set new value to attribute with name if it's exist. 
        
        Call __setattr__ method of super class otherwise.
        
        """
        attr = self.attributesProps.get(name, None)
        node = self.nodesProps.get(name, None)
        if attr:
            value = self._validate(name, attr, value, setter=True)
            self.cleanAttribute(attr.xmlattr)
            if value is not None:
                self.attributes[attr.xmlattr] = unicode(value)
        elif node:
            if value is None and node.required:
                raise ElementParseError, 'required node %s is not specified' % name
            self.removeChilds(name=node.xmlnode)
            if not node.listed or value is None:
                values = (value,)
            else:
                values = value
            for value in values:
                content = self._validate(name, node, value, setter=True)
                if isinstance(content, MyElement):
                    self.addChild(content)
                elif isinstance(content, EmptyElement) or content is None:
                    pass
                else:
                    n = MyElement((None, node.xmlnode))
                    n.addChild(unicode(content))
                    self.addChild(n)
        else:
            super(MyElement, self).__setattr__(name, value)

    def topElement(self):
        """
        Return top element in elements hierarchy.
        
        :returns:  
            self if instance have not parent elements
            
            top element of parent element otherwise
            
        """
        parent = getattr(self, 'parent', None)
        if parent:
            return parent.topElement()
        return self

    def _content_get(self):
        """
        Getter for property descriptor.
        Return content.
        
        :returns: unicode content
        
        :raises: ValueError
        
        """
        r = u''
        for c in self.children:
            if not isinstance(c, (unicode, str)):
                raise ValueError
            r += c
        return r

    def _content_set(self, value):
        """
        Setter for property descriptor.
        Remove old content.
        Set value as content.        
        """
        self.removeChilds()
        self.children.append(unicode(value))
    content = property(_content_get, _content_set)

    def addElement(self, name, defaultUri=None, content=None):
        """
        Append element to childrens. 
        Return element with specified name, Uri and content.
        """
        result = None
        if isinstance(name, tuple):
            if defaultUri is None:
                defaultUri = name[0]
            self.children.append(MyElement(name, defaultUri))
        else:
            if defaultUri is None:
                defaultUri = self.defaultUri
            self.children.append(MyElement((defaultUri, name), defaultUri))

        result = self.children[-1]
        result.parent = self

        if content:
            result.children.append(content)

        return result

    def cleanAttribute(self, attrib):
        """Delete attribute if it's exist."""
        if self.hasAttribute(attrib):
            del self.attributes[attrib]

    def removeChilds(self, name=None, uri=None, element=None):
        """
        Remove all content and child elements appropriate 
        to name-uri pair.
        """
        if element is not None:
            name = element.elementName
            uri = getattr(element, 'elementUri', None)
        children = []
        for el in self.children:
            if not isinstance(el, (str, unicode)) and \
               not (el.name == name and (uri is None or el.uri == uri)):
                children.append(el)
        self.children = children

    def link(self, el):
        """
        Link query to stanza.
        """
        self.removeChilds(el.name, el.uri)
        self.addChild(el)
        result_class = getattr(el, 'result_class')
        if result_class is not None:
            self.result_class = result_class
        error_class = getattr(el, 'error_class')
        if error_class is not None:
            self.error_class = error_class
