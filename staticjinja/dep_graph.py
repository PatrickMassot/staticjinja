# -*- coding:utf-8 -*-

"""
Dependency graph for staticjina
"""

from copy import deepcopy


class DepGraph(object):
    """
    A directed graph which will handle dependencies between templates and data
    files in a site.

    :param parents:
        A dictionary whose keys are vertices of the graph and each value is the
        set of child vertices of the key vertex.

    :param children:
        A dictionary whose keys are vertices of the graph and each value is the
        set of parents vertices of the key vertex.

    """
    def __init__(self, parents, children):
        self.parents = parents
        self.children = children

    @classmethod
    def from_parents(cls, parents):
        """
        Buils a graph from a dictionnary of directed edges
        by building the dictionnary of children edges.

        :param parents:
            A dictionary whose keys are vertices of the graph and each value is
            the set of child vertices of the key vertex.
        """
        children = {}
        for filename in parents:
            children[filename] = set()
        for filename in parents:
            for d in parents[filename]:
                children[d].add(filename)
            print(children)
        return cls(parents, children)

    def connected_components(self, direction, start):
        """Returns the (directed) connected component of start in the graph.

        Uses a classical depth first search.

        :param direction: either 'descendants' or 'ancestors'

        :param start: the vertex in the graph whose connected component we
        seek.
        """

        if direction == 'descendants':
            adjacency = self.children
        elif direction == 'ancestors':
            adjacency = self.parents
        else:
            raise ValueError(
                    'direction should be either descendants or ancestors'
                    )

        seen = set([start])
        stack = [iter(adjacency[start])]
        while stack:
            children = stack[-1]
            try:
                child = next(children)
                if child not in seen:
                    yield child
                    seen.add(child)
                    stack.append(iter(adjacency[child]))
            except StopIteration:
                stack.pop()

    def get_descendants(self, filename):
        """Returns all descendants of the given template or data file.

        :param filename: the template or data file whose descendant we seek.
        """
        return self.connected_components('descendants', filename)

    def update(self, filename, new_parents):
        """
        Updates the part of this dependency graph directly linked to some
        template or data file.

        :param filename: A string giving the relative path of the template or
        data file.

        :param new_parents: the new set of parents of filename.
        """
        old_parents = self.parents.get(filename, set())
        if new_parents != old_parents:
            for lost_parent in old_parents.difference(new_parents):
                self.children[lost_parent].remove(filename)
            for new_parent in new_parents.difference(old_parents):
                self.children[new_parent].add(filename)
            self.parents[filename] = new_parents
