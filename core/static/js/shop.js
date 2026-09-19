(function ($) {
    'use strict';

    /* ------------------------------------------------------------------
     * Product detail gallery (Nest theme)
     *
     * The slider settings below are the theme's original ones. They used
     * to live inline inside productDetails() and run once, at
     * document.ready, against every .product-image-slider on the page.
     *
     * That only works when the slides are already in the HTML. A gallery
     * whose <figure> elements arrive later (product detail page: images
     * come from the API) was being slick()-ed while still empty, which
     * left .slick-initialized on the container. slick's init() is a no-op
     * on an element that already carries that class, so the later,
     * "real" init silently skipped buildOut() - no .slick-list, no
     * .slick-track, no .slick-slide - and every theme CSS rule for the
     * gallery stopped matching.
     *
     * So: the init is now a function, galleries marked
     * data-gallery="dynamic" are left alone here, and whoever fills them
     * calls window.NestGallery.init() once the markup is in place.
     * ------------------------------------------------------------------ */

    var ZOOM_OPTIONS = {
        zoomType: 'inner',
        cursor: 'crosshair',
        zoomWindowFadeIn: 500,
        zoomWindowFadeOut: 750
    };

    function applyZoom($img) {
        if (!$img || !$img.length) return;
        if (!$.fn.elevateZoom) return;
        if ($(window).width() <= 768) return;

        var img = $img[0];
        // elevateZoom reads the image's natural size at init time. For an
        // API image that hasn't finished downloading yet that is 0x0 and
        // the zoom overlay ends up mis-sized, so wait for the load event.
        if (!img.complete || !img.naturalWidth) {
            $img.off('load.nestZoom').one('load.nestZoom', function () {
                applyZoom($img);
            });
            return;
        }

        $('.zoomWindowContainer,.zoomContainer').remove();
        $img.elevateZoom(ZOOM_OPTIONS);
    }

    function initDetailGallery(gallery) {
        var $gallery = $(gallery);
        if (!$gallery.length) return;

        var $main = $gallery.find('.product-image-slider').first();
        var $thumbs = $gallery.find('.slider-nav-thumbnails').first();
        if (!$main.length) return;

        // A container that was sliced earlier (e.g. while it was still
        // empty) has to be torn down first, otherwise slick skips
        // buildOut() and the slides never get their theme markup.
        if ($main.hasClass('slick-initialized')) $main.slick('unslick');
        if ($thumbs.length && $thumbs.hasClass('slick-initialized')) $thumbs.slick('unslick');

        if (!$main.children().length) return; // nothing to show yet

        var hasThumbs = $thumbs.length > 0 && $thumbs.children().length > 0;

        $main.slick({
            slidesToShow: 1,
            slidesToScroll: 1,
            arrows: false,
            fade: false,
            asNavFor: hasThumbs ? $thumbs : null
        });

        if (hasThumbs) {
            $thumbs.slick({
                slidesToShow: 4,
                slidesToScroll: 1,
                asNavFor: $main,
                dots: false,
                focusOnSelect: true,

                prevArrow: '<button type="button" class="slick-prev"><i class="fi-rs-arrow-small-left"></i></button>',
                nextArrow: '<button type="button" class="slick-next"><i class="fi-rs-arrow-small-right"></i></button>'
            });

            // Remove active class from all thumbnail slides
            $thumbs.find('.slick-slide').removeClass('slick-active');

            // Set active class to first thumbnail slides
            $thumbs.find('.slick-slide').eq(0).addClass('slick-active');

            // On before slide change match active thumbnail to current slide
            $main.on('beforeChange.nestGallery', function (event, slick, currentSlide, nextSlide) {
                $thumbs.find('.slick-slide').removeClass('slick-active');
                $thumbs.find('.slick-slide').eq(nextSlide).addClass('slick-active');
            });
        }

        //Elevate Zoom
        $main.on('beforeChange.nestGallery', function (event, slick, currentSlide, nextSlide) {
            applyZoom($(slick.$slides[nextSlide]).find('img').first());
        });
        applyZoom($main.find('.slick-active img').first());

        // Slides built from API images are usually still downloading when
        // slick measures them, which leaves the track at the wrong
        // height/offset. Re-measure as each image lands.
        $gallery.find('img').on('load.nestGallery', function () {
            if ($main.hasClass('slick-initialized')) $main.slick('setPosition');
            if ($thumbs.length && $thumbs.hasClass('slick-initialized')) $thumbs.slick('setPosition');
        });
    }

    // Public hook for galleries whose slides are injected at runtime.
    window.NestGallery = { init: initDetailGallery };

    /*Product Details*/
    var productDetails = function () {
        // Static galleries (quick-view modal, any hard-coded detail page)
        // initialise here exactly as before. Dynamic ones are initialised
        // by their own page script once the slides exist.
        $('.detail-gallery').not('[data-gallery="dynamic"]').each(function () {
            initDetailGallery(this);
        });

        //Filter color/Size
        $('.list-filter').each(function () {
            $(this).find('a').on('click', function (event) {
                event.preventDefault();
                $(this).parent().siblings().removeClass('active');
                $(this).parent().toggleClass('active');
                $(this).parents('.attr-detail').find('.current-size').text($(this).text());
                $(this).parents('.attr-detail').find('.current-color').text($(this).attr('data-color'));
            });
        });

        //Qty Up-Down
        $('.detail-qty').each(function () {
            var qtyval = parseInt($(this).find(".qty-val").val(), 10);
            var $qtyInput = $(this).find(".qty-val");

            $(this).find('.qty-up').on('click', function (event) {
                event.preventDefault();
                qtyval = qtyval + 1;
                $qtyInput.val(qtyval);
            });

            $(this).find(".qty-down").on("click", function (event) {
                event.preventDefault();/*  */
                qtyval = Math.max(1, qtyval - 1);
                $qtyInput.val(qtyval);
            });
        });

        $('.dropdown-menu .cart_list').on('click', function (event) {
            event.stopPropagation();
        });
    };

    //Load functions
    $(document).ready(function () {
        productDetails();
    });

})(jQuery);
