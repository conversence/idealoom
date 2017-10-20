"use strict;"

var CK = require('ckeditor');

var CKEDITOR_CONFIG = {
    toolbar: [
        ['Bold', 'Italic', 'Outdent', 'Indent', 'NumberedList', 'BulletedList'],
        ['Link', 'Unlink', 'Anchor', 'IdealoomExtract']
    ],
    extraPlugins: 'sharedspace,idealoomExtract',
    removePlugins: 'floatingspace,resize',
    sharedSpaces: { top: 'ckeditor-toptoolbar', bottom: 'ckeditor-bottomtoolbar' },
    disableNativeSpellChecker: false,
    title: false //Removes the annoying tooltip in the middle of the main textarea
  };

CKEDITOR.plugins.addExternal('idealoomExtract', static_url + '/js/app/views/reusableDataFields/ckeditor_plugins/idealoomExtract/' );

module.exports = {
  CKEDITOR: CKEDITOR,
  CK: CK,
  CKEDITOR_CONFIG: CKEDITOR_CONFIG,
};
