/**
 * List of the unit tests executed.
 * @module app.tests
 */
import Mocha from "mocha";

mocha.setup("bdd");

// use require instead of import so it comes after setup
require("./tests/routes.spec.js");
require("./tests/context.spec.js");
require("./tests/models.spec.js");
require("./tests/utils.spec.js");
require("./tests/objects.spec.js");
require("./tests/langstring.spec.js");
require("./tests/views.spec.js");

mocha.run();
