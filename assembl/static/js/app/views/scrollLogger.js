/** Estimated words per minute below which we consider that this is a "Slow" scroll */
const SLOW_SCROLL_WPM_THREASHHOLD = 300;

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
        console.log("TODO: Flush all updates before object is destroyed...");
    }
    /**
     * Return the subset of scroll log stack  entries applicable to the timestamps
     * of a specific message in the message scroll log
     * @param {*} timeStampFirstOnscreen
     * @param {*} timeStampLastOnscreen
     */
    getScrollVectorsForTimeRange(
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

    getViewportGeometry() {
        const currentViewPortTop = this.messageList.getCurrentViewPortTop();
        const currentViewPortBottom = this.messageList.getCurrentViewPortBottom();
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
        const containerSelector = this.messageList.ui.panelBody;

        const scrollableContainerHeight = containerSelector[0].scrollHeight;
        const firstMessageSelector = containerSelector.find(".message").first();
        const lastMessageSelector = containerSelector.find(".message").last();

        const firstMsgOffsetFromTopOfScrollContainer = findOffsetTopUntilElement(
            firstMessageSelector[0],
            this.messageList.ui.panelBody[0]
        );

        const lastMsgDistanceFromBottomOfScrollContainer =
            scrollableContainerHeight -
            findOffsetTopUntilElement(
                lastMessageSelector[0],
                containerSelector[0]
            ) +
            lastMessageSelector[0].scrollHeight;

        if (!currentViewPortTop || !currentViewPortBottom) {
            throw new Error("Unable to compute viewport dimensions");
        }
        let viewportHeight = currentViewPortBottom - currentViewPortTop;
        const retVal = {
            currentViewPortTop,
            currentViewPortBottom,
            scrollableContainerHeight,
            viewportHeight,
            firstMsgOffsetFromTopOfScrollContainer,
            lastMsgDistanceFromBottomOfScrollContainer,
        };
        //console.log(retVal);
        return retVal;
    }
    getMessageGeometry(messageSelector, overrideMessageTop) {
        const messageContentSelector = messageSelector
            .find(".message-body")
            .first();

        if (!messageSelector || messageSelector.length !== 1) {
            console.log(messageSelector);
            throw new Error("getMessageGeometry(): messageSelector is invalid");
        }

        if (!messageContentSelector || messageContentSelector.length !== 1) {
            console.log(messageContentSelector);
            throw new Error(
                "getMessageGeometry(): messageContentSelector is invalid"
            );
        }

        const messageContentDom = messageContentSelector[0];
        const messageDom = messageSelector[0];
        if (messageContentDom.offsetParent.id !== messageSelector[0].id) {
            console.log(messageContentDom.offsetParent, messageSelector);
            throw new Error(
                "getMessageGeometry(): the message content's offsetParent isn't the message. offset calculations wont work.  Most likely the CSS or HTML has changed"
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
            //throw new Error("checkMessagesOnscreen(): Unable to compute message dimensions.");
        }
        const msgTopWhitespaceTop = msgTop;
        const msgTopWhitespaceBottom = msgContentTop;
        const msgTopWhitespaceHeight =
            msgTopWhitespaceBottom - msgTopWhitespaceTop;
        const msgBottomWhitespaceTop = msgContentBottom;
        const msgBottomWhitespaceBottom = msgBottom;
        const msgBottomWhitespaceHeight =
            msgBottomWhitespaceBottom - msgBottomWhitespaceTop;

        /*
            let //15px message padding bottom
          messageWhiteSpaceRatio = (messageSelector.find(".js_messageHeader").height() + messageSelector.find(".js_messageContentBottomMenu").height() - 15) / msgContentHeight;
          */
        const retVal = {
            msgTop,
            msgHeight,
            msgBottom,
            msgContentTop,
            msgContentHeight,
            msgContentBottom,
            msgWidth,
            msgTopWhitespaceTop,
            msgTopWhitespaceBottom,
            msgTopWhitespaceHeight,
            msgBottomWhitespaceTop,
            msgBottomWhitespaceBottom,
            msgBottomWhitespaceHeight,
        };
        //console.log(retVal);
        return retVal;
    }
    getContentVisibleFractions(viewportGeometry, contentTop, contentHeight) {
        const {
            currentViewPortTop,
            currentViewPortBottom,
            viewportHeight,
        } = viewportGeometry;
        /*console.log(
            "getContentVisibleFractions(): ",
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
        const contentVsViewportRatio = contentHeight / viewportHeight;
        const viewportFractionCovered =
            (fractionInsideViewPort * contentHeight) / viewportHeight;
        const retVal = {
            fractionAboveViewPort,
            fractionBelowViewPort,
            fractionInsideViewPort,
            viewportFractionCovered,
            contentVsViewportRatio,
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
     * @property {number} msgVsViewportRatio - Fraction, can be larger than 1
     * @property {number} msgScrollableDistance - in px, >=0.  The distance one has to scroll for the message to enter and completely leave the viewport
     */
    /**
     *
     * @param {*} messageGeometry
     * @param {*} viewportGeometry
     * @return {messageVsViewportGeometry}
     */
    getMessageVsViewportGeometry(messageGeometry, viewportGeometry) {
        const {
            msgTop,
            msgHeight,
            msgContentTop,
            msgContentHeight,
            msgTopWhitespaceTop,
            msgTopWhitespaceHeight,
            msgBottomWhitespaceTop,
            msgBottomWhitespaceHeight,
        } = messageGeometry;
        const { viewportHeight } = viewportGeometry;

        const {
            fractionAboveViewPort: msgFractionAboveViewPort,
            fractionBelowViewPort: msgFractionBelowViewPort,
            fractionInsideViewPort: msgFractionInsideViewPort,
            viewportFractionCovered: viewportFractionCoveredByMsg,
            contentVsViewportRatio: msgVsViewportRatio,
        } = this.getContentVisibleFractions(
            viewportGeometry,
            msgTop,
            msgHeight
        );
        const {
            fractionInsideViewPort: messageContentFractionInsideViewPort,
            viewportFractionCovered: viewportFractionCoveredByMsgContent,
        } = this.getContentVisibleFractions(
            viewportGeometry,
            msgContentTop,
            msgContentHeight
        );
        const {
            fractionInsideViewPort: wsTopFractionInsideViewPort,
            viewportFractionCovered: wsTopViewportFractionCoveredByMsg,
        } = this.getContentVisibleFractions(
            viewportGeometry,
            msgTopWhitespaceTop,
            msgTopWhitespaceHeight
        );
        const {
            fractionInsideViewPort: wsBottomFractionInsideViewPort,
            viewportFractionCovered: wsBottomViewportFractionCoveredByMsg,
        } = this.getContentVisibleFractions(
            viewportGeometry,
            msgBottomWhitespaceTop,
            msgBottomWhitespaceHeight
        );
        const viewportFractionCoveredByMsgWhitespace =
            wsTopViewportFractionCoveredByMsg +
            wsBottomViewportFractionCoveredByMsg;
        const msgScrollableDistance = msgHeight + viewportHeight;

        const retVal = {
            msgFractionAboveViewPort,
            msgFractionBelowViewPort,
            msgFractionInsideViewPort,
            viewportFractionCoveredByMsgWhitespace,
            viewportFractionCoveredByMsgContent,
            viewportFractionCoveredByMsg,
            msgVsViewportRatio,
            msgScrollableDistance,
        };
        //console.log(retVal);
        return retVal;
    }

    /**
     * Computes which messages are currently onscreen
     * @param {*} resultMessageIdCollection
     * @param {*} visitorData
     */
    checkMessagesOnscreen(resultMessageIdCollection, visitorData) {
        let that = this;
        let messageSelectors = this.messageList.getOnScreenMessagesSelectors(
            resultMessageIdCollection,
            visitorData
        );

        let currentScrollTop = this.messageList.ui.panelBody.scrollTop();
        if (currentScrollTop === undefined) {
            throw new Error("Unable to compute viewport scrollTop");
        }
        //TODO: While unlikely the height has changed spotaneously during scroll, it is very possible that a message has been expanded from preview, or that the thread branch has been collapsed.  The scroll scrollEvents do not log this.  To fix  "properly", we would need to timestamp individual message size change.  A quick and more realistic improvement would be to immediately force a final update when the message changed geometry, and prune it's history.  It could be done during checkMessagesOnscreen.

        const viewportGeometry = this.getViewportGeometry();
        const { currentViewPortTop, currentViewPortBottom } = viewportGeometry;
        let latestScrollEventAtStart =
            that.scrollEventStack[that.scrollEventStack.length - 1];
        let previousScrollEventAtStart =
            that.scrollEventStack[that.scrollEventStack.length - 2];

            console.log(
                "checkMessagesOnscreen() for ",
                latestScrollEventAtStart,
                previousScrollEventAtStart,
                that.scrollEventStack
            );
        if (previousScrollEventAtStart) {
            this.processMsgForScrollEvent(
                viewportGeometry,
                messageSelectors,
                latestScrollEventAtStart,
                previousScrollEventAtStart
            );
            if (false && this.debugScrollLogging) {
                //console.log(messageSelectors);
                console.log(
                    "checkMessagesOnscreen() starts at currentScrollTop:",
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
                that.pruneOldScrollEvents(oldestMessageInLogTimeStamp);
            }
        }
    }

    /**
     * Prune all scroll event older than the last one PRIOR to the
     * timestamp provided
     * @param {*} timeStamp
     */
    pruneOldScrollEvents(timeStamp) {
        let that = this;

        if (!timeStamp) {
            throw new Error(
                "pruneOldScrollEvents: missing or invalid timestamp"
            );
        }
        let firstNewerVectorIndex = that.scrollEventStack.findIndex(
            (scrollEvent) => {
                if (scrollEvent.timeStamp === undefined) {
                    throw new Error(
                        "pruneOldScrollEvents: Unable to process scrollEvent"
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
    getMessageLogTemplate() {
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
                effectiveWpmIfUserReadWholeMessage: undefined,
            },
        });
    }

    computeAttentionRepartitionGlobal(msgGeometryMap) {
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
     * Compute attention repartition for everything onscreen for a single scroll scrollEvent
     * @param {*} scrollEvent
     * @returns {}
     */
    processMsgForScrollEvent(
        viewportGeometry,
        messageSelectors,
        scrollEvent,
        previousScrollEvent
    ) {
        const msgGeometryMap = new Map();
        for (let messageSelector of messageSelectors) {
            if (!messageSelector || messageSelector.length == 0) return;

            let messageId = messageSelector[0].id;
            let messageGeometry = this.getMessageGeometry(messageSelector);

            let { msgTop } = messageGeometry;
            let messageVsViewportGeometry = this.getMessageVsViewportGeometry(
                messageGeometry,
                viewportGeometry
            );
            let {
                msgFractionInsideViewPort,
                viewportFractionCoveredByMsgContent,
                viewportFractionCoveredByMsgWhitespace,
            } = messageVsViewportGeometry;

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
                        this.getMessageLogTemplate()
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
                /*const scrollEvents = this.getScrollVectorsForTimeRange(
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

        /* 
                                                          const previousScrollEvent = scrollEvents[idx - 1];
                            if (idx !== 0) 
                //Skip the first scrollEvent, as it's the one BEFORE the message was onscreen.  We need it as a reference to establish speed.
                */
        const scrollEventsInfo = this.processScrollVector(
            scrollEvent,
            previousScrollEvent,
            msgGeometryMap,
            viewportGeometry
        );

        Object.values(this.loggedMessages).map((messageLog) => {
            if (this.debugScrollLogging) {
                let messageInfo = {
                    _internal: _,
                    ...messageLog,
                };
                console.log(
                    "Mock-wrote new log for message",
                    messageLog.messageId,
                    ": ",
                    messageInfo
                );
            }
        });
    }

    /** Compute the direction of the scroll
                Reminder:  scrollTop is the position of the scrollBar, so always positive
                top() of an element is the distance from top of the container, also always positive
                So, scrolling UP (content moves up), scrollTop increases
                When reading, we expect direction to be UP
                
         * @param {number} distance - px
         */
    getDirection(distance) {
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
     * @param {*} scrollLoggerMessageInfo The attention information last logged about the message
     * @param {*} scrollEvents
     * @param {*} messageSelector
     */
    processScrollVector(
        scrollEvent,
        previousScrollEvent,
        msgGeometryMap,
        viewportGeometry
    ) {
        let that = this;
        const attentionRepartitionGlobal = this.computeAttentionRepartitionGlobal(
            msgGeometryMap
        );
        console.log(attentionRepartitionGlobal);
        //console.log(this.loggedMessages);
        this.loggedMessages.forEach((messageLog, messageId) => {
            console.log("processScrollVector for messageId", messageLog);
            const messageGeometryInfo = msgGeometryMap.get(messageId);
            if (!messageGeometryInfo) {
                throw new Error(
                    `Geometry information is missing for message ${messageId}`
                );
            }
            const { messageVsViewportGeometry } = messageGeometryInfo;
            const messageSelector = messageLog._internal.messageSelector;

            const CURRENT_FONT_SIZE_PX = parseFloat(
                messageSelector.find(".message-body").first().css("font-size")
            );
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

            const distancePx =
                scrollEvent.scrollTop - previousScrollEvent.scrollTop;
            messageLog.metrics.numScrollEvents++;

            const {
                viewportFractionCoveredByMsg,
                msgScrollableDistance,
            } = messageVsViewportGeometry;

            const previousDirection = messageLog._internal.lastValidDirection;
            const direction = that.getDirection(distancePx);

            if (direction !== DIRECTION_NONE) {
                //We actually moved
                messageLog._internal.lastValidDirection = direction;
            }
            if (
                direction !== DIRECTION_NONE && //We actually moved
                previousDirection && //Not the first movement
                previousDirection !== direction
            ) {
                //We changed direction
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
            const elapsedMilliseconds =
                scrollEvent.timeStamp - previousScrollEvent.timeStamp;

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

                /** Imagine a 100px msg, and 1000px viewport.  The total distance to scroll for the message to enter or leave screen is 1100px.  The first 100px, it's partially onscreen.  The last 100px, it's partially onscreen. When it's fully onscreen, it only represents 10% of the viewport.
                    The total distance to cover is viewport + size of message, even if the message is bigger than the viewport.
                    The effective distance is the estimated equivalent distance scrolled inside the message.
                    In the example above, we want after scrolling
                    50px: 50/1100
                    100px: 100/1100
                    550px: 550/1100 == 50%
                    1100px: 1100/1100 == 100%
          
                    If we backed-off 300 px to re-read something, and then finished scrolling, we'd have
                    1400px: 1400/1100
                    */
                const currEffectiveFractionOfMessageScrolled =
                    distancePx / msgScrollableDistance;
                messageLog.metrics.totalEffectiveFractionOfMessageScrolled += currEffectiveFractionOfMessageScrolled;
                const fractionOfTotalUpScroll =
                    distancePx / messageLog._internal.cumulativeUpDistancePx;
                const scrollLines = distancePx / ESTIMATED_LINE_HEIGHT;

                const scrollLinesPerMinute =
                    (scrollLines / elapsedMilliseconds) * 1000 * 60;
                const rawSrollWordsPerMinute =
                    scrollLinesPerMinute * WORDS_PER_LINE;
                /** The viewport isn't just composed of content.  This is the effective scroll speed in words per minute if the the content of all messages in the viewport constituted the entire content. */
                const effectiveSrollWordsPerMinute =
                    attentionRepartitionGlobal.viewportFractionContent *
                    rawSrollWordsPerMinute;
                console.log(
                    rawSrollWordsPerMinute,
                    effectiveSrollWordsPerMinute
                );
                if (messageLog.metrics.scrollUpAvgEffectiveWPM) {
                    messageLog.metrics.scrollUpAvgEffectiveWPM =
                        fractionOfTotalUpScroll * effectiveSrollWordsPerMinute +
                        (1 - fractionOfTotalUpScroll) *
                            messageLog.metrics.scrollUpAvgEffectiveWPM;
                } else {
                    messageLog.metrics.scrollUpAvgEffectiveWPM = effectiveSrollWordsPerMinute;
                }
                //Règle de 3...
                messageLog.metrics.effectiveWpmIfUserReadWholeMessage =
                    messageLog.metrics.scrollUpAvgEffectiveWPM /
                    messageLog.metrics.totalEffectiveFractionOfMessageScrolled;
            }
        });
    }
}

export default ScrollLogger;
