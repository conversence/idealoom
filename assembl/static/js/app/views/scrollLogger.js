import Ctx from "../common/context.js";

/** Estimated words per minute below which we consider that this is a "Slow" scroll */
const SLOW_SCROLL_WPM_THREASHHOLD = 300;
/** After 1 minute, we consider the user wasn't reading since the last interval.  A more refined metric would be the time required to read a wall of text in the viewport at 150 WPM  */
const SCROLL_TIMEOUT_MS = 1000 * 60 * 1;

/** How often to compute message read statistics from scrolling */
const SCROLL_VECTOR_MEASUREMENT_INTERVAL = 300; //milliseconds, needs to be substantially faster than time between users conscious scroll events
const DIRECTION_DOWN = "DIRECTION_DOWN";
const DIRECTION_UP = "DIRECTION_UP";
const DIRECTION_NONE = "DIRECTION_NONE"; //No movement
const ATTENTION_UPDATE_INITIAL = "INITIAL";
const ATTENTION_UPDATE_INTERIM = "INTERIM";
const ATTENTION_UPDATE_FINAL = "FINAL";
const ATTENTION_UPDATE_NONE = "NONE";

class ScrollLogger {
    constructor(messageList) {
        this.debugScrollLogging = true;
        this.messageList = messageList;
        this.scrollEventStack = [];
        this.loggedMessages = new Map();
    }

    static getScrollLogInterval() {
        return SCROLL_VECTOR_MEASUREMENT_INTERVAL;
    }

    finalize() {
        this._flushToServerAndReset();
    }
    /**
     * Return the subset of scroll log stack  entries applicable to the timestamps
     * of a specific message in the message scroll log
     * @param {*} timeStampFirstOnscreen
     * @param {*} timeStampLastOnscreen
     */
    _getScrollVectorsForTimeRange(
        timeStampFirstOnscreen,
        timeStampLastOnscreen
    ) {
        var that = this;
        function checkApplicability(scrollEvent, index, arr) {
            return (
                scrollEvent.timeStamp <= timeStampLastOnscreen &&
                (scrollEvent.timeStamp >= timeStampFirstOnscreen ||
                    arr[index + 1].timeStamp >= timeStampFirstOnscreen) //We also want the scroll that brought the message onscreen, so we peek ahead...
            );
        }
        let applicableVectors = that.scrollEventStack.filter(
            checkApplicability
        );
        return applicableVectors;
    }

    _getViewportGeometry() {
        const currentViewPortTop = this.messageList.getCurrentViewPortTop();
        const currentViewPortBottom = this.messageList.getCurrentViewPortBottom();

        const scrollableContainerSelector = this.messageList.ui.panelBody;

        const scrollableContainerHeight =
            scrollableContainerSelector[0].scrollHeight;

        if (!currentViewPortTop || !currentViewPortBottom) {
            throw new Error("Unable to compute viewport dimensions");
        }
        let viewportHeight = currentViewPortBottom - currentViewPortTop;
        const retVal = {
            currentViewPortTop,
            currentViewPortBottom,
            scrollableContainerHeight,
            scrollableContainerSelector,
            viewportHeight,
        };
        //console.log(retVal);
        return retVal;
    }
    _getMessageGeometry(messageSelector, overrideMessageTop) {
        const messageContentSelector = messageSelector
            .find(".message-body")
            .first();

            if (
                !messageSelector ||
                messageSelector.length == 0 ||
                messageSelector[0].scrollHeight == 0
            ) {
                //The tread is collapsed, or the messages has been paged-out
                //console.log("Invalid message selector", messageSelector);
                return;
            }
        if (!messageContentSelector || messageContentSelector.length !== 1) {
            console.log(messageContentSelector);
            throw new Error(
                "_getMessageGeometry(): messageContentSelector is invalid"
            );
        }

        const messageContentDom = messageContentSelector[0];
        const messageDom = messageSelector[0];
        if (messageContentDom.offsetParent.id !== messageSelector[0].id) {
            console.log(messageContentDom.offsetParent, messageSelector);
            throw new Error(
                "_getMessageGeometry(): the message content's offsetParent isn't the message. offset calculations wont work.  Most likely the CSS or HTML has changed"
            );
        }
        //console.log(messageSelector, messageSelector.height(), messageDom.scrollHeight,  messageContentDom.style.marginTop, messageContentDom.style.marginTop, messageContentDom.style.borderTop);
        // TODO: Consider using the height of the message body, which would give more accurate values for most assumptions, at the cost of completely ignoring whitespace and title.
        const msgTop = overrideMessageTop
            ? overrideMessageTop
            : messageSelector.offset().top;
        const messageContentOffsetTop = messageContentDom.offsetTop;
        const msgContentTop = msgTop + messageContentOffsetTop;
        const msgHeight = messageDom.scrollHeight;

        const msgBottom = msgTop + msgHeight;
        const msgContentHeight = messageContentDom.scrollHeight;
        const msgWidth = messageSelector.width();
        const msgContentBottom = msgContentTop + msgContentHeight;
        if (
            !msgContentTop ||
            !msgContentHeight ||
            !msgContentBottom ||
            !msgWidth
        ) {
            console.log(
                "TODO:  Unable to compute message dimensions. Need to handle case when thread has been collapsed"
            );
            //throw new Error("processScrollEventStack(): Unable to compute message dimensions.");
        }

        /*
            let //15px message padding bottom
          messageWhiteSpaceRatio = (messageSelector.find(".js_messageHeader").height() + messageSelector.find(".js_messageContentBottomMenu").height() - 15) / msgContentHeight;
          */
        const retVal = {
            messageSelector,
            msgTop,
            msgHeight,
            msgBottom,
            msgContentTop,
            msgContentHeight,
            msgContentBottom,
            messageContentSelector,
            msgWidth,
        };
        //console.log(retVal);
        return retVal;
    }
    _getContentVisibleFractions(viewportGeometry, contentTop, contentHeight) {
        const {
            currentViewPortTop,
            currentViewPortBottom,
            viewportHeight,
        } = viewportGeometry;
        /*console.log(
            "_getContentVisibleFractions(): ",
            viewportGeometry,
            contentTop,
            contentHeight
        );*/
        if (!contentHeight) {
            throw new Error("content has no height");
        }

        const contentBottom = contentTop + contentHeight;
        let topDistanceAboveViewPort = currentViewPortTop - contentTop;
        let bottomDistanceBelowViewPort = contentBottom - currentViewPortBottom;

        let fractionInsideViewPort;
        let fractionAboveViewPort;
        let fractionBelowViewPort;

        if (topDistanceAboveViewPort < 0) {
            fractionAboveViewPort = 0;
        } else {
            fractionAboveViewPort = Math.min(
                topDistanceAboveViewPort / contentHeight,
                1
            );
        }

        if (bottomDistanceBelowViewPort < 0) {
            fractionBelowViewPort = 0;
        } else {
            fractionBelowViewPort = Math.min(
                bottomDistanceBelowViewPort / contentHeight,
                1
            );
        }

        fractionInsideViewPort =
            1 - fractionAboveViewPort - fractionBelowViewPort;
        const msgContentVsViewportRatio = contentHeight / viewportHeight;
        const viewportFractionCovered =
            (fractionInsideViewPort * contentHeight) / viewportHeight;
        const retVal = {
            fractionAboveViewPort,
            fractionBelowViewPort,
            fractionInsideViewPort,
            viewportFractionCovered,
            msgContentVsViewportRatio,
        };
        //console.log(retVal);
        return retVal;
    }
    /**
     * @typedef {messageVsViewportGeometry}
     * @property {number} msgFractionAboveViewPort - Fraction, 0 to 1
     * @property {number} msgFractionBelowViewPort - Fraction, 0 to 1
     * @property {number} msgFractionInsideViewPort - Fraction, 0 to 1
     * @property {number} viewportFractionCoveredByMsg - Fraction, 0 to 1
     * @property {number} msgContentVsViewportRatio - Fraction, can be larger than 1
     * @property {number} msgContentRealScrollableDistance - in px, >=0.  The distance one has to scroll for the message to enter and completely leave the viewport
     */
    /**
     *
     * @param {*} messageGeometry
     * @param {*} viewportGeometry
     * @return {messageVsViewportGeometry}
     */
    _getMessageVsViewportGeometry(messageGeometry, viewportGeometry) {
        const {
            messageContentSelector,
            msgTop,
            msgHeight,
            msgContentTop,
            msgContentHeight,
        } = messageGeometry;
        const {
            viewportHeight,
            scrollableContainerHeight,
            scrollableContainerSelector,
        } = viewportGeometry;

        const {
            fractionAboveViewPort: msgFractionAboveViewPort,
            fractionBelowViewPort: msgFractionBelowViewPort,
            fractionInsideViewPort: msgFractionInsideViewPort,
            viewportFractionCovered: viewportFractionCoveredByMsg,
            msgContentVsViewportRatio,
        } = this._getContentVisibleFractions(
            viewportGeometry,
            msgTop,
            msgHeight
        );
        const {
            fractionInsideViewPort: messageContentFractionInsideViewPort,
            viewportFractionCovered: viewportFractionCoveredByMsgContent,
        } = this._getContentVisibleFractions(
            viewportGeometry,
            msgContentTop,
            msgContentHeight
        );

        function findOffsetTopUntilElement(element, targetParentElement) {
            //console.log("findOffsetTopUntilElement()",element.offsetTop,element, element.offsetParent, targetParentElement);
            if (element.offsetParent !== targetParentElement) {
                return (
                    element.offsetTop +
                    findOffsetTopUntilElement(
                        element.offsetParent,
                        targetParentElement
                    )
                );
            } else {
                return element.offsetTop;
            }
        }
        const containerScrollTop = scrollableContainerSelector[0].scrollTop;
        const containerClientHeight =
            scrollableContainerSelector[0].clientHeight;
        const contentBottomOffsetFromTopOfScrollContainer =
            findOffsetTopUntilElement(
                messageContentSelector[0],
                scrollableContainerSelector[0]
            ) + msgContentHeight;
        const unscrollableSpaceTop = Math.max(
            containerClientHeight - contentBottomOffsetFromTopOfScrollContainer,
            0
        );
        const contentTopOffsetFromBottomOfScrollContainer =
            scrollableContainerHeight -
            findOffsetTopUntilElement(
                messageContentSelector[0],
                scrollableContainerSelector[0]
            );
        const unscrollableSpaceBottom = Math.max(
            containerClientHeight - contentTopOffsetFromBottomOfScrollContainer,
            0
        );
        /** The total distance the message content can travel in the viewport.  Normally viewport height + size of message content, even if the message is bigger than the viewport. */
        const msgContentNormalScrollableDistance =
            msgContentHeight + viewportHeight;
        /**However, this is corrected in the case the viewport cannot scroll that far for messages near the top or bottem of the content. */
        const msgContentRealScrollableDistance =
            msgContentNormalScrollableDistance -
            unscrollableSpaceTop -
            unscrollableSpaceBottom;
        /*console.log({
            contentBottomOffsetFromTopOfScrollContainer,
            contentTopOffsetFromBottomOfScrollContainer,
            viewportHeight,
            containerClientHeight,
            containerScrollTop,
            unscrollableSpaceTop,
            unscrollableSpaceBottom,
            msgContentRealScrollableDistance,
        });*/
        const retVal = {
            msgFractionAboveViewPort,
            msgFractionBelowViewPort,
            msgFractionInsideViewPort,
            viewportFractionCoveredByMsgContent,
            viewportFractionCoveredByMsg,
            msgContentVsViewportRatio,
            msgContentNormalScrollableDistance,
            msgContentRealScrollableDistance,
        };
        //console.log(retVal);
        return retVal;
    }

    /**
     * Prune all scroll event older than the last one PRIOR to the
     * timestamp provided
     * @param {*} timeStamp
     */
    _getMessageLogTemplate(timeStamp) {
        let that = this;

        if (!timeStamp) {
            throw new Error(
                "_getMessageLogTemplate: missing or invalid timestamp"
            );
        }
        let firstNewerVectorIndex = that.scrollEventStack.findIndex(
            (scrollEvent) => {
                if (scrollEvent.timeStamp === undefined) {
                    throw new Error(
                        "_getMessageLogTemplate: Unable to process scrollEvent"
                    );
                }
                return scrollEvent.timeStamp >= timeStamp;
            }
        );

        //console.log("firstNewerVectorIndex ", firstNewerVectorIndex, "newer than", timeStamp);
        let lastIndexToKeep = firstNewerVectorIndex - 1; //We also need the scrollEvent that brought the message onscreen, which is just before the one when the message was detected onscreen.
        if (lastIndexToKeep >= 0) {
            //console.log("pruning scrollEvents indexes  0 to ", lastIndexToKeep);
            that.scrollEventStack.splice(0, lastIndexToKeep + 1);
        }
    }

    _getMessageLogTemplate() {
        return _.clone({
            _internal: {
                lastValidDirection: undefined,
                cumulativeDownDistancePx: 0,
                cumulativeUpDistancePx: 0,
            },
            metrics: {
                totalDurationMs: 0,
                numScrollEvents: 0,
                numDirectionChanges: 0,
                numDirectionChangesWhileMessageCoversViewport: 0,
                numEstimatedInternalDirectionChanges: 0,
                scrollUpAvgEffectiveWPM: undefined,
                numSlowScrolls: "TODO",
                fractionInSlowScrolls: "TODO",
                totalEffectiveFractionOfMessageScrolled: 0,
                effectiveTimeSpentOnMessage: "TODO",
                effectiveWpmIfUserReadWholeMessage: undefined,
            },
        });
    }

    /**
     * Computes the global fraction of the viewport currently occupied by content and non-content.
     *
     * @param {*} msgGeometryMap
     */
    _computeAttentionRepartitionGlobal(msgGeometryMap) {
        let viewportFractionContent = 0;
        for (const [key, value] of msgGeometryMap) {
            //console.log(key, value);
            viewportFractionContent +=
                value.messageVsViewportGeometry
                    .viewportFractionCoveredByMsgContent;
        }
        const retVal = {
            viewportFractionContent,
            viewportFractionNonContent: 1 - viewportFractionContent,
        };
        return retVal;
    }

    /**
     * Compute the direction of the scroll
     * Reminder:  scrollTop is the position of the scrollBar, so always positive top() of an element is the distance from top of the container, also always positive.
     * So, scrolling UP (content moves up), scrollTop increases
     * When reading, we expect direction to be UP
     * @param {number} distance - px
     */
    _getDirection(distance) {
        if (distance === 0) {
            return DIRECTION_NONE;
        }
        switch (distance / Math.abs(distance)) {
            case -1:
                return DIRECTION_DOWN;
            case 1:
                return DIRECTION_UP;
            default:
                console.log("distance:", distance);
                throw new Error("Unable to compute scroll direction");
        }
    }
    /**
     * Calculates the actual attention signal the scroll movement implies for each message.
     */
    _computeAttentionSignals(
        scrollEvent,
        previousScrollEvent,
        msgGeometryMap,
        viewportGeometry
    ) {
        let that = this;
        const attentionRepartitionGlobal = this._computeAttentionRepartitionGlobal(
            msgGeometryMap
        );
        //console.log(attentionRepartitionGlobal);
        const distancePx =
            scrollEvent.scrollTop - previousScrollEvent.scrollTop;
        const direction = that._getDirection(distancePx);
        const elapsedMilliseconds =
            scrollEvent.timeStamp - previousScrollEvent.timeStamp;

        if (false && that.debugScrollLogging) {
            const scrollPxPerMinute =
                (distancePx / elapsedMilliseconds) * 1000 * 60;
            console.log(
                `_computeAttentionSignals(), scrolled ${distancePx}px in ${elapsedMilliseconds}ms; ${scrollPxPerMinute} px/min`
            );
        }
        //console.log(this.loggedMessages);
        this.loggedMessages.forEach((messageLog, messageId) => {
            //console.log("_computeAttentionSignals for messageId", messageId);
            const messageGeometryInfo = msgGeometryMap.get(messageId);
            if (!messageGeometryInfo) {
                return;
            }
            const { messageVsViewportGeometry } = messageGeometryInfo;
            const messageSelector = messageLog._internal.messageSelector;

            const CURRENT_FONT_SIZE_PX = parseFloat(
                messageSelector.find(".message-body").first().css("font-size")
            );
            //WARNING TODO:  The px and font size does not change depending on the browser's zoom.  Solution https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport
            if (!CURRENT_FONT_SIZE_PX) {
                throw new Error("Unable to detemine current font size");
            }

            //Note:  After testing, the width() (a jquery function) is the proper
            // content width, as a float, excluding padding and margins.
            const messageTextWidth = messageSelector.width();

            //Character per line:  normally between 45 to 75, 66 is considered ideal.
            //Average character per line = div width / font size in px*0.4
            const CURRENT_CHARACTERS_PER_LINE =
                messageTextWidth / (CURRENT_FONT_SIZE_PX * 0.4);

            //(gotcha:  ideally substract non-character size of message, but still count header)
            const ESTIMATED_LINE_HEIGHT = 1.5 * CURRENT_FONT_SIZE_PX;

            //Character per word: 5.1 average for english language + 1 space => multipy WPM*5 to get CPM
            const CARACTERS_PER_WORD = 5.1 + 1;

            let WORDS_PER_LINE =
                CURRENT_CHARACTERS_PER_LINE / CARACTERS_PER_WORD;

            if (false && that.debugScrollLogging) {
                console.log("CURRENT_FONT_SIZE_PX", CURRENT_FONT_SIZE_PX);
                console.log("messageTextWidth", messageTextWidth);
                console.log(
                    "CURRENT_CHARACTERS_PER_LINE",
                    CURRENT_CHARACTERS_PER_LINE
                );
                console.log("ESTIMATED_LINE_HEIGHT", ESTIMATED_LINE_HEIGHT);
                console.log("CARACTERS_PER_WORD", CARACTERS_PER_WORD);
                console.log("WORDS_PER_LINE", WORDS_PER_LINE);
                console.log("CURRENT_FONT_SIZE_PX", CURRENT_FONT_SIZE_PX);
            }

            messageLog.metrics.numScrollEvents++;

            const {
                viewportFractionCoveredByMsg,
                msgContentNormalScrollableDistance,
                msgContentRealScrollableDistance,
            } = messageVsViewportGeometry;

            const previousDirection = messageLog._internal.lastValidDirection;

            if (direction !== DIRECTION_NONE) {
                //We actually moved
                messageLog._internal.lastValidDirection = direction;
            }
            if (
                direction !== DIRECTION_NONE && //We actually moved
                previousDirection && //Not the first movement
                previousDirection !== direction //We changed direction
            ) {
                messageLog.metrics.numDirectionChanges += 1;
                if (viewportFractionCoveredByMsg >= 1) {
                    //An internal message scroll to re-read something, very strong
                    //attention signal
                    messageLog.metrics.numDirectionChangesWhileMessageCoversViewport += 1;
                }
                messageLog.metrics.numEstimatedInternalDirectionChanges +=
                    1 * viewportFractionCoveredByMsg;
            }

            /* Distance metrics */

            messageLog.metrics.totalDurationMs += elapsedMilliseconds;
            if (direction === DIRECTION_DOWN) {
                messageLog._internal.cumulativeDownDistancePx += Math.abs(
                    distancePx
                );
            }
            if (direction === DIRECTION_UP) {
                messageLog._internal.cumulativeUpDistancePx += Math.abs(
                    distancePx
                );

                /** Imagine a 100px msg, and 1000px viewport.  The total distance to scroll for the message to enter and leave screen is 1100px.  The first 100px, it's partially onscreen.  The last 100px, it's partially onscreen. When it's fully onscreen, it only represents 10% of the viewport.
                    The total distance to cover is viewport + size of message, even if the message is bigger than the viewport.
                    The effective fraction of the message scrolled is the portion of the total message travel that has actually been scrolled.
                    In the example above, we want after scrolling
                    50px: 50/1100
                    100px: 100/1100
                    550px: 550/1100 == 50%
                    1100px: 1100/1100 == 100%
          
                    If we backed-off 300 px to re-read something, and then finished scrolling, we'd have
                    1400px: 1400/1100

                    The above illustrates the concept of msgContentNormalScrollableDistance. 
                    
                    However, messages at the top and bottom of the viewport have a lower msgContentRealScrollableDistance that the example above, as they cannot scroll this far before the scrollbar bumps at the end of their travel.
                    */
                const currEffectiveFractionOfMessageScrolled =
                    distancePx / msgContentRealScrollableDistance;

                messageLog.metrics.totalEffectiveFractionOfMessageScrolled += currEffectiveFractionOfMessageScrolled;

                const scrollLines = distancePx / ESTIMATED_LINE_HEIGHT;

                const scrollLinesPerMinute =
                    (scrollLines / elapsedMilliseconds) * 1000 * 60;
                const rawScrollWordsPerMinute =
                    scrollLinesPerMinute * WORDS_PER_LINE;
                /** The viewport isn't just composed of content.  The following is the effective scroll speed in words per minute if the content of all messages in the viewport constituted the entire content.  Since the content is only a part of the screen, it's as if the user scrolled slower (in WPM), as we presume he only reads text...
                 *
                 * Furthermore, messages near the top or bottom of the message list cannot travel the entire viewport because they would bump at the top or bottom of the scrollbar.  In practice, this means the user has likely started to read before the scroll for messages at the top, and kept reading after the last scroll at the bottom.  So we compensate for that.
                 *
                 * WARNING:  This assumes there is no infinite scroll.  If infinite scroll is implemented, either is must be triggered one vieuport in advance, which completely avoids the problem.  Alternatively, we can ignore the correction for messages towards the end of the viewport, but this doesn't give exact result in the case (for example) there is only a single short message to be brought onscreen thru infinite scrolling
                 */
                const effectiveScrollWordsPerMinute =
                    attentionRepartitionGlobal.viewportFractionContent *
                    rawScrollWordsPerMinute *
                    (msgContentNormalScrollableDistance /
                        msgContentRealScrollableDistance);
                /*console.log(
                    "rawScrollWordsPerMinute",
                    rawScrollWordsPerMinute,
                    "effectiveScrollWordsPerMinute",
                    effectiveScrollWordsPerMinute,
                    "px to words factor",
                    (1 / ESTIMATED_LINE_HEIGHT) * WORDS_PER_LINE
                );*/

                if (messageLog.metrics.scrollUpAvgEffectiveWPM) {
                    /*
                The new average scroll speed cannot simply be obtained by total scroll distance / total time.  While the factor to obtain rawScrollWordsPerMinute is at least constant per message, the factor to obtain effectiveScrollWordsPerMinute per minutes is different for every scroll position.  Instead of memorising the terms for every scroll and recomputing here, we do some math to obtain the new value.
                
                We'll explain the formula as if all speed were in px/s
                Say we have:
                cD = cumulative distance scrolled
                dD = distance scrolled during new scroll
                cS = cumulative average speed in px/s
                dS = speed during new scroll in px/s
                cSWPM = cumulative speed in WPM
                sSWPM = speed of current scroll in WPM
                cT = cumulative time elapsed before current scroll
                dT = Time elapsed during current scroll
                cF = Constant to transform cumulative speed to effective scrollSpeed
                dF = Constant to transform current speed to effective scrollSpeed
                nS = New cumulative speed in px/s

                We have (obviously):
                (cD + dD) / (cT + dT) = nS in px/s

                We can transform to:

                (cS*cT + dS*dT) / (cT + dT) = nS in px/s
                
                Note that the above no longer depends on the px unit, so the correction factors can be applied to speeds
                (cF*cS*cT + dF*dS*dT) / (cT + dT) = nS in WPM

                but cF*cS and df*dS are the speeds in WPM we have, so it becomes 
                (cSWPM*cT + dSWPM*dT) / (cT + dT) = nS in WPM
                */
                    let cT =
                        messageLog.metrics.totalDurationMs -
                        elapsedMilliseconds; //At this stage, messageLog.metrics.totalDurationMs has already been recomputed...
                    let dT = elapsedMilliseconds;
                    let cSWPM = messageLog.metrics.scrollUpAvgEffectiveWPM;
                    let dSWPM = effectiveScrollWordsPerMinute;
                    /*console.log("Before:", {
                        cT,
                        dT,
                        cSWPM,
                        dSWPM,
                        fractionOfTotalUpScroll,
                    });*/
                    messageLog.metrics.scrollUpAvgEffectiveWPM =
                        (cSWPM * cT + dSWPM * dT) / (cT + dT);
                    /*console.log(
                        "After:",
                        messageLog.metrics.scrollUpAvgEffectiveWPM
                    );*/
                } else {
                    messageLog.metrics.scrollUpAvgEffectiveWPM = effectiveScrollWordsPerMinute;
                }

                //Règle de 3...
                messageLog.metrics.effectiveWpmIfUserReadWholeMessage =
                    messageLog.metrics.scrollUpAvgEffectiveWPM /
                    messageLog.metrics.totalEffectiveFractionOfMessageScrolled;
            }
        });
    }

    /**
     * Finds every message that is at least partially in the current viewport,
     * and for each one log attention signal generated for the scrollEvent
     */
    _logScrollForMessagesInViewport(
        viewportGeometry,
        messageSelectors,
        scrollEvent,
        previousScrollEvent
    ) {
        const msgGeometryMap = new Map();
        for (let messageSelector of messageSelectors) {
            if (
                !messageSelector ||
                messageSelector.length == 0 ||
                messageSelector[0].scrollHeight == 0
            ) {
                //The tread is collapsed, or the messages has been paged-out
                //console.log("Invalid message selector", messageSelector);
                break;
            }
            let messageId = messageSelector[0].id;
            let messageGeometry = this._getMessageGeometry(messageSelector);

            let { msgTop } = messageGeometry;
            let messageVsViewportGeometry = this._getMessageVsViewportGeometry(
                messageGeometry,
                viewportGeometry
            );
            let { msgFractionInsideViewPort } = messageVsViewportGeometry;

            msgGeometryMap.set(messageId, {
                messageGeometry,
                messageVsViewportGeometry,
            });
            let updateType;

            let existingLog = this.loggedMessages.get(messageId);
            if (!existingLog) {
                if (msgFractionInsideViewPort > 0) {
                    updateType = ATTENTION_UPDATE_INITIAL;
                    this.loggedMessages.set(
                        messageId,
                        this._getMessageLogTemplate()
                    );
                } else {
                    updateType = ATTENTION_UPDATE_NONE;
                }
            } else {
                if (msgFractionInsideViewPort > 0) {
                    updateType = ATTENTION_UPDATE_INTERIM;
                } else {
                    updateType = ATTENTION_UPDATE_FINAL;
                }
            }
            if (updateType !== ATTENTION_UPDATE_NONE) {
                let timeStampFirstOnscreen;
                let timeStampLastOnscreen;
                let msgTopWhenFirstOnscreen;

                switch (updateType) {
                    case ATTENTION_UPDATE_INITIAL:
                        timeStampFirstOnscreen = scrollEvent.timeStamp;
                        timeStampLastOnscreen = scrollEvent.timeStamp;
                        msgTopWhenFirstOnscreen = msgTop;
                        break;
                    case ATTENTION_UPDATE_INTERIM:
                        timeStampFirstOnscreen =
                            existingLog.timeStampFirstOnscreen;
                        timeStampLastOnscreen = scrollEvent.timeStamp;
                        msgTopWhenFirstOnscreen =
                            existingLog._internal.msgTopWhenFirstOnscreen;
                        break;
                    case ATTENTION_UPDATE_FINAL: //Basically, repeat last interim
                        timeStampFirstOnscreen =
                            existingLog.timeStampFirstOnscreen;
                        timeStampLastOnscreen =
                            existingLog.timeStampLastOnscreen;
                        msgTopWhenFirstOnscreen =
                            existingLog._internal.msgTopWhenFirstOnscreen;
                        break;
                    default:
                        throw new Error("Unknown update type");
                }
                /*const scrollEvents = this._getScrollVectorsForTimeRange(
                    timeStampFirstOnscreen,
                    timeStampLastOnscreen
                );
                */
                let messageLog = this.loggedMessages.get(messageId);

                //An update with the same updateid replaces the previous one
                messageLog.updateId = messageId + "_" + timeStampFirstOnscreen;
                messageLog.messageId = messageId;
                messageLog.updateType = updateType;
                messageLog.timeStampFirstOnscreen = timeStampFirstOnscreen;
                messageLog._internal.msgTopWhenFirstOnscreen = msgTopWhenFirstOnscreen;
                messageLog._internal.messageSelector = messageSelector;
            } else {
                //Update type is NONE
                if (msgTop > viewportGeometry.currentViewPortBottom) {
                    //All messages are in DOM order, no reason to keep crunching messages
                    break;
                }
            }
        }
        //console.log(msgGeometryMap);

        const scrollEventsInfo = this._computeAttentionSignals(
            scrollEvent,
            previousScrollEvent,
            msgGeometryMap,
            viewportGeometry
        );

        this._flushToServer();
    } //End _logScrollForMessagesInViewport()

    _flushToServer(flushAsFinal = false) {
        this.loggedMessages.forEach((messageLog) => {
            const updateType = flushAsFinal
                ? ATTENTION_UPDATE_FINAL
                : messageLog.updateType;
            let { _internal, ...messageInfo } = messageLog;
            const user = Ctx.getCurrentUser().id;
            messageInfo = { ...messageInfo, user, updateType };
            if (this.debugScrollLogging) {
                console.log(
                    "Mock-wrote new log for message",
                    messageLog.messageId,
                    ": ",
                    messageInfo
                );
            }
        });
    }

    _flushToServerAndReset() {
        this._flushToServer(true);
        this.loggedMessages = new Map();
        //Keep exactly one event, in case this is due to a timeout.  In which case, we won't lose the the exact time the user resumed reading
        this.scrollEventStack.splice(0, this.scrollEventStack.length - 1);
    }
    /**
     * This function must be called once each time a scoll event is appended to the stack.  It will call all logging function, and clean up obsolete data from memory
     * @param {*} resultMessageIdCollection
     * @param {*} visitorData
     */
    processScrollEventStack(resultMessageIdCollection, visitorData) {
        let that = this;
        let messageSelectors = this.messageList.getOnScreenMessagesSelectors(
            resultMessageIdCollection,
            visitorData
        );

        let currentScrollTop = this.messageList.ui.panelBody.scrollTop();
        if (currentScrollTop === undefined) {
            throw new Error("Unable to compute viewport scrollTop");
        }

        const viewportGeometry = this._getViewportGeometry();
        const { currentViewPortTop, currentViewPortBottom } = viewportGeometry;
        let latestScrollEventAtStart =
            that.scrollEventStack[that.scrollEventStack.length - 1];
        let previousScrollEventAtStart =
            that.scrollEventStack[that.scrollEventStack.length - 2];

        /*console.log(
            "processScrollEventStack() for ",
            latestScrollEventAtStart,
            previousScrollEventAtStart
        );*/
        if (previousScrollEventAtStart) {
            if (
                //If the user didn't come back to his screen after a trip to the coffee machine
                latestScrollEventAtStart.timeStamp -
                    previousScrollEventAtStart.timeStamp >
                SCROLL_TIMEOUT_MS
            ) {
                if (this.debugScrollLogging) {
                    console.log(
                        "Scroll timeout excedded, send final update for previous log and reset"
                    );
                }
                this._flushToServerAndReset();
                return;
            }
            this._logScrollForMessagesInViewport(
                viewportGeometry,
                messageSelectors,
                latestScrollEventAtStart,
                previousScrollEventAtStart
            );
            if (false && this.debugScrollLogging) {
                //console.log(messageSelectors);
                console.log(
                    "processScrollEventStack() starts at currentScrollTop:",
                    currentScrollTop
                );
            }

            let oldestMessageInLogTimeStamp = 0;
            for (const [id, log] of this.loggedMessages) {
                if (log.updateType === ATTENTION_UPDATE_FINAL) {
                    if (that.debugScrollLogging) {
                        console.log(
                            "message",
                            id,
                            " processed FINAL update, deleting from log..."
                        );
                    }
                    this.loggedMessages.delete(id);
                } else {
                    if (!log.timeStampFirstOnscreen) {
                        throw new Error("timeStampFirstOnscreen is invalid");
                    }
                    if (
                        !oldestMessageInLogTimeStamp ||
                        log.timeStampFirstOnscreen < oldestMessageInLogTimeStamp
                    ) {
                        oldestMessageInLogTimeStamp =
                            log.timeStampFirstOnscreen;
                    }
                }
            }

            //console.log(oldestMessageInLogTimeStamp, that.loggedMessages);
            if (oldestMessageInLogTimeStamp) {
                that._getMessageLogTemplate(oldestMessageInLogTimeStamp);
            }
        }
    }
}

export default ScrollLogger;
