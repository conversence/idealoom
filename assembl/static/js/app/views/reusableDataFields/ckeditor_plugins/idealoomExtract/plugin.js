'use strict;'

CKEDITOR.plugins.add( 'idealoomExtract', {
  requires: 'widget',

  icons: 'idealoomExtract',

  init: function( editor ) {
    editor.widgets.add( 'idealoomExtract', {
      button: 'Add a web quote',
      template:
        '<div class="idealoomExtract">' +
            '<blockquote class="quote-content"></blockquote>' +
            '<div class="quote-attribution"></div>' +
            '<div class="quote-url"></div>' +
        '</div>',
          allowedContent: 'div(!idealoomExtract); a[href](!quote-origin); div(!quote-attribution);blockquote(!quote-content)',
          requiredContent: 'div(idealoomExtract)',
          pathName: 'idealoomExtract',

      upcast: function( element ) {
        return element.name == 'div' && element.hasClass( 'idealoomExtract' );
      },
    });
    editor.on( 'paste', function( evt ) {
      var segment = evt.data.dataTransfer.getData( 'segment' );
      if ( !segment ) {
        return;
      }
      try {
        segment = JSON.parse(segment);
      } catch (e) {
        return;
      }
      var value =
        '<div class="idealoomExtract" id="'+segment.id+'">' +
            '<blockquote class="quote-content">'+segment.quote+'</blockquote>';
      if (segment.creatorName) {
        value += '<div class="quote-attribution">'+segment.creatorName+'</div>';
      }
      if (segment.url) {
        value += '<a class="quote-origin" href="'+segment.url+'">original</a>';
      } else if (segment.idPost) {
        value += '<a class="quote-origin" href="#+'+segment.idPost+'">original post</a>';
      }
      evt.data.dataValue = value + '</div>';
    } );
  },

} );
