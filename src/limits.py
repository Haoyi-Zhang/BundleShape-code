"""Admission limits shared as data, not as normalization logic."""

FORMAT = "iwb-1"
MAX_FILES = 64
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
# Event/rule/declaration limits are aggregate per bundle, not per resource.
MAX_EVENTS = 10000
MAX_RULES = 4000
MAX_DECLARATIONS = 8000
MAX_NAME_LENGTH = 80
MAX_PATH_LENGTH = 240
MAX_CERT_BYTES = 4 * 1024 * 1024

FORBIDDEN_TAGS = {
    "script", "form", "input", "button", "textarea", "select", "option",
    "iframe", "frame", "frameset", "object", "embed", "applet", "base",
    "portal", "template",
}

ALLOWED_TAGS = {
    "html", "head", "body", "title", "meta", "link", "div", "span", "p",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "nav",
    "main", "header", "footer", "article", "section", "aside", "img", "a",
    "strong", "em", "small", "figure", "figcaption", "br", "hr",
}

VOID_TAGS = {"meta", "link", "img", "br", "hr"}

ALLOWED_ATTRS = {
    "id", "class", "href", "src", "rel", "type", "media", "alt", "title",
    "lang", "charset", "name", "content", "role", "width", "height",
}

# Attribute names are not sufficient for admission: the same spelling can have
# a different meaning on a different element.  Global attributes remain small;
# element-specific attributes are accepted only at the listed source anchors.
GLOBAL_ATTRS = {"id", "class", "title", "role", "lang"}
TAG_ATTRS = {
    "html": {"lang"},
    "meta": {"charset", "name", "content"},
    "link": {"href", "rel", "type", "media"},
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
}

REFERENCE_ATTRS = {"href", "src"}

# Longhands only. Duplicate properties, shorthands, custom properties, fallbacks,
# and !important are rejected, so declaration order is irrelevant in this model.
ALLOWED_PROPERTIES = {
    "color", "background-color", "border-top-color", "border-right-color",
    "border-bottom-color", "border-left-color", "border-top-style",
    "border-right-style", "border-bottom-style", "border-left-style",
    "border-top-width", "border-right-width", "border-bottom-width",
    "border-left-width", "border-top-left-radius", "border-top-right-radius",
    "border-bottom-right-radius", "border-bottom-left-radius", "display",
    "position", "top", "right", "bottom", "left", "z-index", "overflow-x",
    "overflow-y", "opacity", "visibility", "width", "height", "min-width",
    "max-width", "min-height", "max-height", "margin-top", "margin-right",
    "margin-bottom", "margin-left", "padding-top", "padding-right",
    "padding-bottom", "padding-left", "font-family", "font-size", "font-style",
    "font-weight", "line-height", "letter-spacing", "text-align",
    "text-decoration-line", "text-transform", "white-space", "list-style-type",
    "object-fit", "vertical-align", "cursor", "row-gap", "column-gap",
    "grid-template-columns", "grid-template-rows", "grid-column-start",
    "grid-column-end", "grid-row-start", "grid-row-end", "justify-content",
    "align-items", "align-content", "flex-direction", "flex-grow",
    "flex-shrink", "order", "box-sizing", "background-image",
}
