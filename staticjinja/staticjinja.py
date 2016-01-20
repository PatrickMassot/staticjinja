# -*- coding:utf-8 -*-

"""
Simple static page generator.

Uses Jinja2 to compile templates.
"""

from __future__ import absolute_import, print_function

import inspect
import logging
import os
import re
import shutil
import warnings

from jinja2 import Environment, FileSystemLoader

from .reloader import Reloader
from .sources import Sources


def _has_argument(func):
    """Test whether a function expects an argument.

    :param func:
        The function to be tested for existence of an argument.
    """
    if hasattr(inspect, 'signature'):
        # New way in python 3.3
        sig = inspect.signature(func)
        return bool(sig.parameters)
    else:
        # Old way
        return bool(inspect.getargspec(func).args)


class Site(object):
    """The Site object.

    :param environment:
        A :class:`jinja2.Environment`.

    :param sources:
        A :class:`Sources` tracking all sources of the website.

    :param searchpath:
        A string representing the name of the directory to search for
        templates.

    :param outpath:
        A string representing the name of the directory that the Site
        should store rendered files in. Defaults to ``'.'``.

    :param encoding:
        The encoding of templates to use.

    :param logger:
        A logging.Logger object used to log events.

    :param contexts:
        A list of `regex, context` pairs. Each context is either a dictionary
        or a function that takes either no argument or or the current template
        as its sole argument and returns a dictionary. The regex, if matched
        against a filename, will cause the context to be used.

    :param rules:
        A list of `regex, function` pairs used to override template
        compilation. `regex` must be a regex which if matched against a
        filename will cause `function` to be used instead of the default.
        `function` must be a function which takes a Jinja2 Environment, the
        filename, and the context and renders a template.

    :param mergecontexts:
        A boolean value. If set to ``True``, then all matching regex from the
        contexts list will be merged (in order) to get the final context.
        Otherwise, only the first matching regex is used. Defaults to
        ``False``.
    """

    def __init__(self,
                 environment,
                 sources,
                 searchpath,
                 outpath,
                 encoding,
                 logger,
                 contexts=None,
                 rules=None,
                 mergecontexts=False,
                 ):
        self._env = environment
        self.sources = sources
        self.searchpath = searchpath
        self.outpath = outpath
        self.encoding = encoding
        self.logger = logger
        self.contexts = contexts or []
        self.rules = rules or []
        self.mergecontexts = mergecontexts

    @property
    def templates(self):
        """Generator for templates."""
        for template_name in self.sources.template_names:
            yield self.get_template(template_name)

    def get_template(self, template_name):
        """Get a :class:`jinja2.Template` from the environment.

        :param template_name: A string representing the name of the template.
        """
        return self._env.get_template(template_name)

    def get_context(self, template):
        """Get the context for a template.

        If no matching value is found, an empty context is returned.
        Otherwise, this returns either the matching value if the value is
        dictionary-like or the dictionary returned by calling it with
        *template* if the value is a function.

        If several matching values are found, the resulting dictionaries will
        be merged before being returned if mergecontexts is True. Otherwise,
        only the first matching value is returned.

        :param template: the template to get the context for
        """
        context = {}
        for regex, context_generator in self.contexts:
            if re.match(regex, template.name):
                if inspect.isfunction(context_generator):
                    if _has_argument(context_generator):
                        context.update(context_generator(template))
                    else:
                        context.update(context_generator())
                else:
                    context.update(context_generator)

                if not self.mergecontexts:
                    break
        return context

    def get_rule(self, template_name):
        """Find a matching compilation rule for a function.

        Raises a :exc:`ValueError` if no matching rule can be found.

        :param template_name: the name of the template
        """
        for regex, render_func in self.rules:
            if re.match(regex, template_name):
                return render_func
        raise ValueError("no matching rule")

    def _ensure_dir(self, template_name):
        """Ensure the output directory for a template exists."""
        head = os.path.dirname(template_name)
        if head:
            file_dirpath = os.path.join(self.outpath, head)
            if not os.path.exists(file_dirpath):
                os.makedirs(file_dirpath)

    def render_template(self, template, context=None, filepath=None):
        """Render a single :class:`jinja2.Template` object.

        If a Rule matching the template is found, the rendering task is
        delegated to the rule.

        :param template:
            A :class:`jinja2.Template` to render.

        :param context:
            Optional. A dictionary representing the context to render
            *template* with. If no context is provided, :meth:`get_context` is
            used to provide a context.

        :param filepath:
            Optional. A file or file-like object to dump the complete template
            stream into. Defaults to to ``os.path.join(self.outpath,
            template.name)``.

        """
        self.logger.info("Rendering %s..." % template.name)

        if context is None:
            context = self.get_context(template)
        try:
            rule = self.get_rule(template.name)
        except ValueError:
            self._ensure_dir(template.name)
            if filepath is None:
                filepath = os.path.join(self.outpath, template.name)
            template.stream(**context).dump(filepath, self.encoding)
        else:
            rule(self, template, **context)

    def render_templates(self, filenames, outpath=None):
        """Render a collection of templates names.

        :param filenames:
            A collection of path to templates to render.

        :param outpath:
            Optional. A file or file-like object to dump the complete template
            stream into. Defaults to to ``os.path.join(self.outpath,
            template.name)``.

        """
        for filename in filenames:
            self.render_template(self._env.get_template(filename), outpath)

    def copy_static(self, files):
        for f in files:
            input_location = os.path.join(self.searchpath, f)
            output_location = os.path.join(self.outpath, f)
            print("Copying %s to %s." % (f, output_location))
            self._ensure_dir(f)
            shutil.copy2(input_location, output_location)

    def render(self, use_reloader=False):
        """Generate the site.

        :param use_reloader: if given, reload templates on modification
        """
        self.render_templates(list(self.sources.template_names))
        self.copy_static(self.sources.static_names)

        if use_reloader:
            self.logger.info("Watching '%s' for changes..." %
                             self.searchpath)
            self.logger.info("Press Ctrl+C to stop.")

            # We build the dep_graph needed for smart reload
            self.sources.make_dep_graph()
            Reloader(self).watch()

    def __repr__(self):
        return "Site('%s', '%s')" % (self.searchpath, self.outpath)


class Renderer(Site):
    def __init__(self, *args, **kwargs):
        warnings.warn("Renderer was renamed to Site.")
        super(Renderer, Site).__init__(*args, **kwargs)

    def run(self, use_reloader=False):
        return self.render(use_reloader)


def make_site(searchpath="templates",
              outpath=".",
              contexts=None,
              rules=None,
              encoding="utf8",
              extensions=None,
              staticpaths=None,
              datapaths=None,
              extra_deps=None,
              filters=None,
              env_kwargs=None,
              mergecontexts=False):
    """Create a :class:`Site <Site>` object.

    :param searchpath:
        A string representing the absolute path to the directory that the Site
        should search to discover templates. Defaults to ``'templates'``.

        If a relative path is provided, it will be coerced to an absolute path
        by prepending the directory name of the calling module. For example, if
        you invoke staticjinja using ``python build.py`` in directory ``/foo``,
        then *searchpath* will be ``/foo/templates``.

    :param outpath:
        A string representing the name of the directory that the Site
        should store rendered files in. Defaults to ``'.'``.

    :param contexts:
        A list of *(regex, context)* pairs. The Site will render templates
        whose name match *regex* using *context*. *context* must be either a
        dictionary-like object or a function that takes either no arguments or
        a single :class:`jinja2.Template` as an argument and returns a
        dictionary representing the context. Defaults to ``[]``.

    :param rules:
        A list of *(regex, function)* pairs. The Site will delegate
        rendering to *function* if *regex* matches the name of a template
        during rendering. *function* must take a :class:`jinja2.Environment`
        object, a filename, and a context as parameters and render the
        template. Defaults to ``[]``.

    :param encoding:
        A string representing the encoding that the Site should use when
        rendering templates. Defaults to ``'utf8'``.

    :param extensions:
        A list of :ref:`Jinja extensions <jinja-extensions>` that the
        :class:`jinja2.Environment` should use. Defaults to ``[]``.

    :param staticpaths:
        List of directories to get static files from (relative to searchpath).
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

    :param filters:
        A dictionary of Jinja2 filters to add to the Environment.
        Defaults to ``{}``.

    :param env_kwargs:
        A dictionary that will be passed as keyword arguments to the
        jinja2 Environment. Defaults to ``{}``.

    :param mergecontexts:
        A boolean value. If set to ``True``, then all matching regex from the
        contexts list will be merged (in order) to get the final context.
        Otherwise, only the first matching regex is used. Defaults to
        ``False``.
    """

    if env_kwargs is None:
        env_kwargs = {}
    env_kwargs['loader'] = FileSystemLoader(searchpath=searchpath,
                                            encoding=encoding)
    env_kwargs.setdefault('extensions', extensions or [])
    environment = Environment(**env_kwargs)
    if filters:
        for k, v in filters.items():
            environment.filters[k] = v

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    sources = Sources.make_sources(
            environment,
            searchpath=searchpath,
            staticpaths=staticpaths,
            datapaths=datapaths,
            extra_deps=extra_deps,
            )

    return Site(
            environment,
            sources,
            searchpath=searchpath,
            outpath=outpath,
            encoding=encoding,
            logger=logger,
            rules=rules,
            contexts=contexts,
            mergecontexts=mergecontexts,
            )


def make_renderer(*args, **kwargs):
    warnings.warn("make_renderer was renamed to make_site.")
    return make_site(*args, **kwargs)
