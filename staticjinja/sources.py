# -*- coding:utf-8 -*-

"""
Sources handler for static jinja

"""

from __future__ import print_function

import os
import inspect
from itertools import chain

from jinja2.meta import find_referenced_templates

from .dep_graph import DepGraph


class Sources(object):
    """
    Handles all source files from a staticjinja website.

    :param environment:
        A :class:`jinja2.Environment`.

    :param searchpath:
        A string representing the name of the directory to search for
        templates.

    :param staticpaths:
        List of directory names to get static files from (relative to
        searchpath).
        Defaults to ``None``.

    :param datapaths:
        List of directories to get data files from (relative to searchpath).
        Defaults to ``None``.

    :param extra_deps:
        List of dependencies on data files. Each dependency is a pair
        (f, d) where f is a (maybe partial) template file path
        and d is a list of data file paths which are used to generate f.
        All path are relative to searchpath.
        Defaults to ``None``.

    """

    def __init__(
            self,
            environment,
            searchpath='templates',
            staticpaths=None,
            datapaths=None,
            extra_deps=None
            ):
        self._env = environment
        self.searchpath = searchpath
        self.staticpaths = staticpaths
        self.datapaths = datapaths
        self.extra_deps = extra_deps

    @classmethod
    def make_sources(
            cls,
            environment,
            searchpath='templates',
            staticpaths=None,
            datapaths=None,
            extra_deps=None
            ):
        """
        Constructs a Sources object after some searchpath wrangling.
        Note that the dep_graph is not constructed. It can be constructed by
        calling make_dep_graph on the resulting object.

        :param environment:
            A :class:`jinja2.Environment`.

        :param searchpath:
            A string representing the name of the directory to search for
            templates.

        :param staticpaths:
            List of directory names to get static files from (relative to
            searchpath).
            Defaults to ``None``.

        :param datapaths:
            List of directories to get data files from (relative to
            searchpath).
            Defaults to ``None``.

        :param extra_deps:
            List of dependencies on data files. Each dependency is a pair
            (f, d) where f is a (maybe partial) template file path
            and d is a list of data file paths which are used to generate f.
            All path are relative to searchpath.
            Defaults to ``None``.

        """

        # Coerce search to an absolute path if it is not already
        if not os.path.isabs(searchpath):
            # TODO: Determine if there is a better way to write do this
            calling_module = inspect.getmodule(inspect.stack()[-1][0])
            # Absolute path to project
            project_path = os.path.realpath(os.path.dirname(
                calling_module.__file__))
            searchpath = os.path.join(project_path, searchpath)

        sources = cls(
            environment,
            searchpath=searchpath,
            staticpaths=staticpaths,
            datapaths=datapaths,
            extra_deps=extra_deps,
            )
        return sources

    @property
    def template_names(self):
        return self._env.list_templates(filter_func=self.is_template)

    @property
    def jinja_names(self):
        return self._env.list_templates(filter_func=self.is_jinja)

    @property
    def static_names(self):
        return self._env.list_templates(filter_func=self.is_static)

    @property
    def data_names(self):
        return self._env.list_templates(filter_func=self.is_data)

    def is_static(self, filename):
        """Check if a file is a static file (which should be copied, rather
        than compiled using Jinja2).

        A file is considered static if it lives in any of the directories
        specified in ``staticpaths``.

        :param filename: the name of the file to check

        """
        if self.staticpaths is None:
            # We're not using static file support
            return False

        for path in self.staticpaths:
            if filename.startswith(path):
                return True
        return False

    def is_data(self, filename):
        """Check if a file is a data file (which should be used by a context
        generator rather than compiled using Jinja2).

        A file is considered data if it lives in any of the directories
        specified in ``datapaths`` or is itself listed in ``datapaths``.

        :param filename: the name of the file to check

        """
        if self.datapaths is None:
            # We're not using data file support
            return False

        for path in self.datapaths:
            if filename.startswith(path):
                return True
        return False

    def is_partial(self, filename):
        """Check if a file is a partial.

        Partial files are not rendered, but they are used in rendering
        templates.

        A file is considered a partial if it or any of its parent directories
        are prefixed with an ``'_'``.

        :param filename: the name of the file to check
        """
        return any((x.startswith("_") for x in filename.split(os.path.sep)))

    def is_ignored(self, filename):
        """Check if a file is an ignored file.

        Ignored files are neither rendered nor used in rendering templates.

        A file is considered ignored if it or any of its parent directories
        are prefixed with an ``'.'``.

        :param filename: the name of the file to check
        """
        return any((x.startswith(".") for x in filename.split(os.path.sep)))

    def is_template(self, filename):
        """Check if a file is a template.

        A file is a considered a template if it is neither a partial nor
        ignored.

        :param filename: the name of the file to check
        """
        if self.is_partial(filename):
            return False

        if self.is_ignored(filename):
            return False

        if self.is_static(filename):
            return False

        if self.is_data(filename):
            return False

        return True

    def is_jinja(self, filename):
        """Check if a file is a data file (which will not be compiled using
        Jinja2 but is presumably used by some context generator).

        A file is considered data if it lives in any of the directories
        specified in ``datapaths`` or is directly mentionned in ``datapaths``.

        :param filename: the name of the file to check

        """
        return self.is_partial(filename) or self.is_template(filename)

    def get_dependencies(self, filename):
        """Get a list of file paths that depends on the file named *filename*
        (relative to searchpath).

        :param filename: the name of the file to find dependencies of
        """
        if self.is_template(filename):
            return [filename]
        elif self.is_partial(filename) or self.is_data(filename):
            return self.dep_graph.get_descendants(filename)
        elif self.is_static(filename):
            return [filename]
        else:
            return []

    def find_jinja_deps(self, filename):
        """Return all (maybe partial) templates extended, imported or included
        by filename.
        """
        # TODO Check whether this function is called only at one place (hence
        # could be integrated)

        source = self._env.loader.get_source(self._env, filename)[0]
        ast = self._env.parse(source)
        return find_referenced_templates(ast)

    def get_file_dep(self, filename):
        """Return a list of path of files which filename depends on."""
        jinja_deps = self.find_jinja_deps(filename)
        if self.extra_deps:
            extra_deps = self.extra_deps.get(filename, [])
        else:
            extra_deps = []

        return set(chain(jinja_deps, extra_deps))

    def update_dep_graph(self, filename):
        """
        Updates self.dep_graph using get_file_name. This shouldn't be called
        before self.make_graph.
        """
        self.dep_graph.update(filename, self.get_file_dep(filename))

    def make_dep_graph(self):
        """
        Builds the dependency graph.
        """
        parents = dict(
                (s, set()) for s in self.jinja_names + self.data_names
                )
        for filename in self.jinja_names:
            parents[filename] = self.get_file_dep(filename)
        self.dep_graph = DepGraph.from_parents(parents)
