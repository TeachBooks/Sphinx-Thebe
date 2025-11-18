"""A sphinx extension to enable interactive computations using thebe."""

import json
import os
from pathlib import Path
from textwrap import dedent
from typing import Optional

from docutils.parsers.rst import Directive
from docutils import nodes
from sphinx.util import logging
import shutil

from wcmatch import glob

from sphinx.locale import get_translation
MESSAGE_CATALOG_NAME = "sphinxthebe"
translate = get_translation(MESSAGE_CATALOG_NAME)

#from ._version import version as __version__

__version__ = "0.3.1"
logger = logging.getLogger(__name__)

THEBE_VERSION = "0.8.2"

SPHINX_THEBE_PRIORITY = 500
THEBE_CONFIG_PRIORITY = 490


def st_static_path(app):
    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "_static"))
    app.config.html_static_path.append(static_path)

    if app.config.thebe_config.get("use_thebe_lite", False):
        thebe_static_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "_thebe_static")
        )
        app.config.html_static_path.append(thebe_static_path)


def init_thebe_default_config(app, env, docnames):
    """Create a default config for fields that aren't given by the user."""
    thebe_config = app.config.thebe_config
    defaults = {
        "always_load": False,
        "selector": ".thebe,.cell",
        "selector_input": "pre",
        "selector_output": ".output, .cell_output",
        "use_thebe_lite": False,
        "exclude_patterns": [],
    }
    for key, val in defaults.items():
        if key not in thebe_config:
            thebe_config[key] = val

    # Standardize types for certain values
    BOOL_KEYS = ["always_load", "use_thebe_lite"]
    for key in BOOL_KEYS:
        thebe_config[key] = _bool(thebe_config[key])


def _bool(b):
    if isinstance(b, bool):
        return b
    else:
        return b in ["true", "True"]


def _has_thebe_cells(doctree):
    """Check if the doctree contains any Thebe-compatible cells."""
    if not doctree:
        return False
    
    # Check for container nodes with 'cell' class (from jupyter notebooks)
    # or literal_block nodes with 'thebe' class (from code-blocks with :class: thebe)
    for node in doctree.traverse():
        # Check for Jupyter notebook cells
        if isinstance(node, nodes.container):
            if 'cell' in node.get('classes', []):
                return True
        # Check for code blocks with thebe class
        if isinstance(node, nodes.literal_block):
            if 'thebe' in node.get('classes', []):
                return True
    
    return False


def _do_load_thebe(doctree, config_thebe):
    """Decide whether to load thebe based on the page's context."""
    # No doctree means there's no page content at all
    if not doctree:
        return False

    # If we aren't properly configured
    if not config_thebe:
        logger.warning(
            "[sphinx-thebe]: Didn't find `thebe_config` in conf.py, add to use thebe"
        )
        return False

    return True


def init_thebe_core(app, env, docnames):
    """Add scripts to configure thebe, and optionally add thebe itself.

    By default, defer loading the `thebe` JS bundle until bootstrap is called
    in order to speed up page load times.
    """
    config_thebe = app.config["thebe_config"]

    # add scripts to the page for translation and configuration
    app.add_js_file(None, body=f"let thebePythonReady = '{translate('Python interaction ready!')}';")
    app.add_js_file(None, body=f"let thebeRunningCells = '{translate('Running pre-initialized cells...')}';")
    app.add_js_file(None, body=f"let thebeLoadingThebe = '{translate('Loading Thebe...')}';")
    app.add_js_file(None, body=f"let thebeWaitingForPackages = '{translate('Waiting for packages to load...')}';")
    app.add_js_file(None, body=f"let thebeLaunchingPyodide = '{translate('Launching Pyodide kernel')}';")
    app.add_js_file(None, body=f"let thebeInitializingThebe = '{translate('Initializing Thebe')}';")
    app.add_js_file(None, body=f"let thebeDeleteCell = '{translate('delete cell')}';")
    app.add_js_file(None, body=f"let thebeDeleteThisCell = '{translate('delete this cell')}';")
    app.add_js_file(None, body=f"let thebeClear = '{translate('clear')}';")
    app.add_js_file(None, body=f"let thebeClearOutput = '{translate('clear the output of the cell')}';")
    app.add_js_file(None, body=f"let thebeAddCell = '{translate('add cell')}';")
    app.add_js_file(None, body=f"let thebeAddNewCell = '{translate('adds a new cell underneath')}';")
    app.add_js_file(None, body=f"let thebeLaunchingBinder = '{translate('Launching from mybinder.org')}';")
    app.add_js_file(None, body=f"let thebeLoadingCDN = '{translate('Loading thebe from CDN...')}';")
    app.add_js_file(None, body=f"let thebeRun = '{translate('run')}';")
    app.add_js_file(None, body=f"let thebeRunCell = '{translate('run this cell')}';")
    app.add_js_file(None, body=f"let thebeRunAll = '{translate('run all')}';")
    app.add_js_file(None, body=f"let thebeRunAllCells = '{translate('run all cells')}';")
    app.add_js_file(None, body=f"let thebeRestartRun = '{translate('restart & run all')}';")
    app.add_js_file(None, body=f"let thebeRestartRunCells = '{translate('restart the kernel and run all cells')}';")
    app.add_js_file(None, body=f"let thebeLiveCode = '{translate('Live Code')}';")
    app.add_js_file(None, body=f"let thebeLaunchThebe = '{translate('Launch Thebe')}';")

    # Minimal i18n injection for CSS overrides
    app.add_js_file(filename="sphinx-thebe-i18n.js")

    app.add_js_file(filename="refresh.js", loading_method="defer")

    if not config_thebe.get("use_thebe_lite", False):
        # Add configuration variables
        THEBE_JS_URL = f"https://unpkg.com/thebe@{THEBE_VERSION}/lib/index.js"
        thebe_config = f"""\
            const THEBE_JS_URL = "{ THEBE_JS_URL }"
            const thebe_selector = "{ app.config.thebe_config['selector'] }"
            const thebe_selector_input = "{ app.config.thebe_config['selector_input'] }"
            const thebe_selector_output = "{ app.config.thebe_config['selector_output'] }"
        """
        app.add_js_file(None, body=dedent(thebe_config))
        app.add_js_file(filename="sphinx-thebe.js", **{"async": "async"})

        if config_thebe.get("always_load") is True:
            # If we've got `always load` on, then load thebe on every page.
            app.add_js_file(THEBE_JS_URL, **{"async": "async"})
    else:
        logger.info("[sphinx-thebe]: Using thebe-lite")
        thebe_config = f"""\
            const thebe_selector = "{ app.config.thebe_config['selector'] }"
            const thebe_selector_input = "{ app.config.thebe_config['selector_input'] }"
            const thebe_selector_output = "{ app.config.thebe_config['selector_output'] }"
        """
        app.add_js_file(None, body=dedent(thebe_config))
        app.add_js_file(
            filename="sphinx-thebe-lite.js",
            loading_method="defer",
            priority=SPHINX_THEBE_PRIORITY,
        )


def update_thebe_context(app, doctree, docname):
    """Add thebe config nodes to this doctree using page-dependent information."""
    config_thebe = app.config["thebe_config"]
    # Skip modifying the doctree if we don't need to load thebe
    if not _do_load_thebe(doctree, config_thebe):
        return

    # Thebe configuration
    if config_thebe is True:
        config_thebe = {}
    if not isinstance(config_thebe, dict):
        raise ValueError(
            "thebe configuration must be `True` or a dictionary for configuration."
        )
    codemirror_theme = config_thebe.get("codemirror-theme", "default")

    # Choose the kernel we'll use
    meta = app.env.metadata.get(docname, {})
    kernel_name = meta.get("thebe-kernel")
    if kernel_name is None:
        if meta.get("kernelspec"):
            if isinstance(meta.get("kernelspec"), str):
                kernel_name = json.loads(meta["kernelspec"]).get("name")
            else:
                kernel_name = meta["kernelspec"].get("name")
        else:
            kernel_name = "python3"

    # Check if this is a Python kernel (for later matplotlib patch injection)
    kernel_name_lower = kernel_name.lower()
    is_python_kernel = "python" in kernel_name_lower or kernel_name_lower.startswith("py") or "-py" in kernel_name_lower or kernel_name_lower.startswith("ipy")

    # Codemirror syntax
    cm_language = kernel_name
    if "python" in cm_language:
        cm_language = "python"
    elif cm_language == "ir":
        cm_language = "r"

    if config_thebe.get("use_thebe_lite", False):
        # If we're using thebe-lite, we populate a different configuration

        # Count the number of slashes, and create a path prefix. If we're
        # in a subdirectory, we need to go up a level for the root path.
        # If we are already at the root, we don't need to go up a level, but still
        # need to add a "./"
        root_path = "/".join([".."] * docname.count("/")) or "./"
        thebe_html_config = f"""
        <script type="text/x-thebe-config">
        {{
            "rootPath": "{root_path}",
            "requestKernel": true,
            "useJupyterLite": true,
            "useBinder": false,
            "kernelOptions": {{
                "path": "/"
            }},
            "codeMirrorConfig": {{
                "theme": "{codemirror_theme}",
                "mode": "{cm_language}"
            }},
            "mountRestartButton": false,
            "mountRestartallButton": false
        }}
        </script>
        """
    else:
        # Create the URL for the kernel request
        repo_url = config_thebe.get(
            "repository_url",
            "https://github.com/binder-examples/jupyter-stacks-datascience",
        )
        branch = config_thebe.get("repository_branch", "master")
        path_to_docs = config_thebe.get("path_to_docs", ".").strip("/") + "/"
        org, repo = _split_repo_url(repo_url)

        # Update the doctree with some nodes for the thebe configuration
        thebe_html_config = f"""
        <script type="text/x-thebe-config">
        {{
            requestKernel: true,
            binderOptions: {{
                repo: "{org}/{repo}",
                ref: "{branch}",
            }},
            codeMirrorConfig: {{
                theme: "{codemirror_theme}",
                mode: "{cm_language}"
            }},
            kernelOptions: {{
                name: "{kernel_name}",
                path: "{path_to_docs}{str(Path(docname).parent)}"
            }},
            predefinedOutput: true
        }}
        </script>
        """

    # Append to the docutils doctree so it makes it into the build outputs
    doctree.append(nodes.raw(text=thebe_html_config, format="html"))
    doctree.append(
        nodes.raw(text=f"<script>kernelName = '{kernel_name}'</script>", format="html")
    )
    
    # Inject matplotlib patch at the start but inside content to avoid button placement issues
    # Patches: https://github.com/TeachBooks/TeachBooks-Sphinx-Thebe/issues/8
    if config_thebe.get("use_thebe_lite", False) and is_python_kernel and _has_thebe_cells(doctree):
        # Minimal patch code without comments to reduce search noise
        matplotlib_patch_code = """import matplotlib
if not hasattr(matplotlib.RcParams, "_get"):
    matplotlib.RcParams._get = dict.get"""
        
        # Create a hidden initialization cell with the patch
        # This cell will auto-execute but remain hidden from users
        matplotlib_patch_html = f"""
<div class="cell docutils container tag_thebe-remove-input-init">
<div class="cell_input docutils container">
<div class="highlight-ipython3 notranslate"><div class="highlight"><pre>{matplotlib_patch_code}</pre>
</div></div></div></div>"""
        
        # Find the first section node and insert at its beginning
        # This ensures it's inside the content section, not before it
        for node in doctree.traverse(nodes.section):
            # Insert as the first child of the first section
            node.insert(0, nodes.raw(text=matplotlib_patch_html, format="html"))
            break
        else:
            # Fallback: if no section found, insert at top of doctree
            doctree.insert(0, nodes.raw(text=matplotlib_patch_html, format="html"))


def _split_repo_url(url):
    """Split a repository URL into an org / repo combination."""
    if "github.com/" in url:
        end = url.split("github.com/")[-1]
        org, repo = end.split("/")[:2]
    else:
        logger.warning(
            f"[sphinx-thebe]: Currently Thebe repositories must be on GitHub, got {url}"
        )
        org = repo = None
    return org, repo


class ThebeButtonNode(nodes.Element):
    """Appended to the doctree by the ThebeButton directive

    Renders as a button to enable thebe on the page.

    If no ThebeButton directive is found in the document but thebe
    is enabled, the node is added at the bottom of the document.
    """

    def __init__(self, rawsource="", *children, text=translate("Run code"), **attributes):
        super().__init__("", text=text)

    def html(self):
        text = self["text"]
        return (
            '<button title="{text}" class="thebelab-button thebe-launch-button" '
            'onclick="initThebe()">{text}</button>'.format(text=text)
        )


class ThebeButton(Directive):
    """Specify a button to activate thebe on the page

    Arguments
    ---------
    text : str (optional)
        If provided, the button text to display

    Content
    -------
    None
    """

    optional_arguments = 1
    final_argument_whitespace = True
    has_content = False

    def run(self):
        kwargs = {"text": self.arguments[0]} if self.arguments else {}
        return [ThebeButtonNode(**kwargs)]


# Used to render an element node as HTML
def visit_element_html(self, node):
    self.body.append(node.html())
    raise nodes.SkipNode


# Used for nodes that do not need to be rendered
def skip(self, node):
    raise nodes.SkipNode


# Helper function to prevent overwriting of files and add some custom ignores when using copytree
# TODO: add pattern matching and add a config for this
def ignore_existing(
    source: Path,
    destination: Path,
    ignored_patterns: Optional[list[str]] = None,
):
    ignored_patterns = ignored_patterns or []

    ignored = [
        Path(path)
        for path in glob.glob(
            ignored_patterns,
            flags=glob.NEGATE
            | glob.GLOBSTAR
            | glob.SPLIT
            | glob.BRACE
            | glob.EXTMATCH
            | glob.CASE,
            root_dir=source,
        )
    ]

    logger.verbose(
        "[Thebe Lite] The following files will not be available through python: {}",
        ignored,
    )

    def _inner(folder: str, contents: list[str]):
        relative_folder = Path(folder).relative_to(source)
        ignore = []

        for content in contents:
            relative_content = relative_folder / content
            if (
                (destination / relative_content).is_file()
                and (destination / relative_content).exists()
            ) or relative_content in ignored:
                ignore.append(content)
        return ignore

    return _inner


def copy_over_files(app, exception):
    thebe_config = app.config["thebe_config"]

    if (exception is not None) or (not thebe_config.get("use_thebe_lite", False)):
        return  # Something has gone wrong or not using thebe lite, let's not bother copying stuff

    ignored_patterns = ["_*/"] + thebe_config.get("exclude_patterns", [])

    shutil.copytree(
        app.srcdir,
        app.outdir,
        symlinks=True,
        dirs_exist_ok=True,
        ignore=ignore_existing(
            app.srcdir, app.outdir, ignored_patterns=ignored_patterns
        ),
    )


def setup(app):

     # add translations
    package_dir = os.path.abspath(os.path.dirname(__file__))
    locale_dir = os.path.join(package_dir, "translations", "locales")
    app.add_message_catalog(MESSAGE_CATALOG_NAME, locale_dir)

    logger.verbose("Adding copy buttons to code blocks...")
    # Add our static path
    app.connect("builder-inited", st_static_path)

    # Set default values for the configuration
    app.connect("env-before-read-docs", init_thebe_default_config)

    # Load the JS/CSS assets for thebe if needed
    app.connect("env-before-read-docs", init_thebe_core)

    # Update the doctree with thebe-specific information if needed
    app.connect("doctree-resolved", update_thebe_context)

    # Copy over all files as symlinks for Python scripts to access
    app.connect("build-finished", copy_over_files)

    # configuration for this tool
    app.add_config_value("thebe_config", {}, "html")

    # override=True in case Jupyter Sphinx has already been loaded
    app.add_directive("thebe-button", ThebeButton, override=True)

    # Add relevant code to headers
    app.add_css_file("sphinx-thebe.css")
    app.add_css_file("thebe.css")
    app.add_css_file("code.css")
    app.add_css_file("dark_mode_widget.css")
    app.add_css_file("thebe-button-patch.css")

    # ThebeButtonNode is the button that activates thebe
    # and is only rendered for the HTML builder
    app.add_node(
        ThebeButtonNode,
        html=(visit_element_html, None),
        latex=(skip, None),
        textinfo=(skip, None),
        text=(skip, None),
        man=(skip, None),
        override=True,
    )

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
