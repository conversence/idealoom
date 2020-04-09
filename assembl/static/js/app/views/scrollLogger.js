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
        this.vectorStack = [];
        this.loggedMessages = {};
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
        function checkApplicability(vector, index, arr) {
            return (
                vector.timeStamp <= timeStampLastOnscreen &&
                (vector.timeStamp >= timeStampFirstOnscreen ||
                    arr[index + 1].timeStamp >= timeStampFirstOnscreen) //We also want the scroll that brought the message onscreen, so we peek ahead...
            );
        }
        let applicableVectors = that.vectorStack.filter(checkApplicability);
        return applicableVectors;
    }

    getViewportGeometry() {
        let currentViewPortTop = this.messageList.getCurrentViewPortTop();
        let currentViewPortBottom = this.messageList.getCurrentViewPortBottom();
        if (!currentViewPortTop || !currentViewPortBottom) {
            throw new Error("Unable to compute viewport dimensions");
        }
        let viewportHeight = currentViewPortBottom - currentViewPortTop;
        return {
            currentViewPortTop,
            currentViewPortBottom,
            viewportHeight,
        };
    }
    getMessageGeometry(messageSelector, overrideMessageTop) {
        if (!messageSelector || messageSelector.length == 0) {
            throw new Error("getMessageGeometry(): messageSelector is invalid");
        }

        // TODO: Consider using the height of the message body, which would give more accurate values for most assumptions, at the cost of completely ignoring whitespace and title.
        let messageTop = overrideMessageTop
            ? overrideMessageTop
            : messageSelector.offset().top;
        let messageHeight = messageSelector.height();
        let messageWidth = messageSelector.width();
        let messageBottom = messageTop + messageHeight;
        if (!messageTop || !messageHeight || !messageBottom || !messageWidth) {
            console.log(
                "TODO:  Unable to compute message dimensions. Need to handle case when thread has been collapsed"
            );
            //throw new Error("checkMessagesOnscreen(): Unable to compute message dimensions.");
        }
        /*
            let //15px message padding bottom
          messageWhiteSpaceRatio = (messageSelector.find(".js_messageHeader").height() + messageSelector.find(".js_messageBottomMenu").height() - 15) / messageHeight;
          */
        return {
            messageTop,
            messageHeight,
            messageBottom,
            messageWidth,
        };
    }

    /**
     * @typedef {messageVsViewportGeometry}
     * @property {number} msgFractionAboveViewPort - Fraction, 0 to 1
     * @property {number} msgFractionBelowViewPort - Fraction, 0 to 1
     * @property {number} msgFractionInsideViewPort - Fraction, 0 to 1
     * @property {number} viewportFractionCoveredByMsg - Fraction, 0 to 1
     * @property {number} msgVsViewportRatio - Fraction, can be larger than 1
     * @property {number} msgScrollableDistance - in px, >=0.  The distance one has to scroll for the message to enter and completely leavec the viewport
     */
    /**
     *
     * @param {*} messageGeometry
     * @param {*} viewportGeometry
     * @return {messageVsViewportGeometry}
     */
    getMessageVsViewportGeometry(messageGeometry, viewportGeometry) {
        const {
            messageTop,
            messageHeight,
            messageWidth,
            messageBottom,
        } = messageGeometry;
        const {
            currentViewPortTop,
            currentViewPortBottom,
            viewportHeight,
        } = viewportGeometry;

        let topDistanceAboveViewPort = currentViewPortTop - messageTop;
        let bottomDistanceBelowViewPort = messageBottom - currentViewPortBottom;

        let msgFractionInsideViewPort;
        let msgFractionAboveViewPort;
        let msgFractionBelowViewPort;

        if (topDistanceAboveViewPort < 0) {
            msgFractionAboveViewPort = 0;
        } else {
            msgFractionAboveViewPort = Math.min(
                topDistanceAboveViewPort / messageHeight,
                1
            );
        }

        if (bottomDistanceBelowViewPort < 0) {
            msgFractionBelowViewPort = 0;
        } else {
            msgFractionBelowViewPort = Math.min(
                bottomDistanceBelowViewPort / messageHeight,
                1
            );
        }

        msgFractionInsideViewPort =
            1 - msgFractionAboveViewPort - msgFractionBelowViewPort;
        const msgVsViewportRatio = messageHeight / viewportHeight;
        const viewportFractionCoveredByMsg =
            (msgFractionInsideViewPort * messageHeight) / viewportHeight;
        const msgScrollableDistance = messageHeight + viewportHeight;
        /*console.log(
      "message topDistanceAboveViewPort ", topDistanceAboveViewPort, "\nbottomDistanceBelowViewPort",bottomDistanceBelowViewPort,
      "\nmessageHeight", messageHeight,
      "\nmsgFractionAboveViewPort", msgFractionAboveViewPort,
      "\nmsgFractionBelowViewPort", msgFractionBelowViewPort,
      "\nmsgFractionInsideViewPort", msgFractionInsideViewPort );*/
        return {
            msgFractionAboveViewPort,
            msgFractionBelowViewPort,
            msgFractionInsideViewPort,
            viewportFractionCoveredByMsg,
            msgVsViewportRatio,
            msgScrollableDistance,
        };
    }

    /**
     * Computes which messages are currently onscreen
     * @param {*} resultMessageIdCollection
     * @param {*} visitorData
     */
    checkMessagesOnscreen(resultMessageIdCollection, visitorData) {
        let that = this;
        let messageDoms = this.messageList.getOnScreenMessagesSelectors(
            resultMessageIdCollection,
            visitorData
        );

        let currentScrollTop = this.messageList.ui.panelBody.scrollTop();
        if (currentScrollTop === undefined) {
            throw new Error("Unable to compute viewport scrollTop");
        }

        const viewportGeometry = this.getViewportGeometry();
        const { currentViewPortTop, currentViewPortBottom } = viewportGeometry;

        if (false && this.debugScrollLogging) {
            //console.log(messageDoms);
            console.log(
                "checkMessagesOnscreen() starts at currentScrollTop:",
                currentScrollTop
            );
        }

        let latestVectorAtStart = that.vectorStack[that.vectorStack.length - 1];
        let previousVectorAtStart =
            that.vectorStack[that.vectorStack.length - 2];
        _.each(messageDoms, function (messageSelector) {
            if (!messageSelector || messageSelector.length == 0) return;
            let messageId = messageSelector[0].id;
            const messageGeometry = that.getMessageGeometry(messageSelector);

            const {
                messageTop,
                messageHeight,
                messageWidth,
                messageBottom,
            } = messageGeometry;
            const messageVsViewportGeometry = that.getMessageVsViewportGeometry(
                messageGeometry,
                viewportGeometry
            );
            const { msgFractionInsideViewPort } = messageVsViewportGeometry;
            let updateType;

            let existingLog = that.loggedMessages[messageId];
            if (!existingLog) {
                if (msgFractionInsideViewPort > 0) {
                    updateType = ATTENTION_UPDATE_INITIAL;
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
                let messageTopWhenFirstOnscreen;

                switch (updateType) {
                    case ATTENTION_UPDATE_INITIAL:
                        timeStampFirstOnscreen = latestVectorAtStart.timeStamp;
                        timeStampLastOnscreen = latestVectorAtStart.timeStamp;
                        messageTopWhenFirstOnscreen = messageTop;
                        break;
                    case ATTENTION_UPDATE_INTERIM:
                        timeStampFirstOnscreen =
                            existingLog.timeStampFirstOnscreen;
                        timeStampLastOnscreen = latestVectorAtStart.timeStamp;
                        messageTopWhenFirstOnscreen =
                            existingLog._internal.messageTopWhenFirstOnscreen;
                        break;
                    case ATTENTION_UPDATE_FINAL: //Basically, repeat last interim
                        timeStampFirstOnscreen =
                            existingLog.timeStampFirstOnscreen;
                        timeStampLastOnscreen = previousVectorAtStart.timeStamp;
                        messageTopWhenFirstOnscreen =
                            existingLog._internal.messageTopWhenFirstOnscreen;
                        break;
                    default:
                        throw new Error("Unknown update type");
                }
                const vectors = that.getScrollVectorsForTimeRange(
                    timeStampFirstOnscreen,
                    timeStampLastOnscreen
                );
                that.loggedMessages[messageId] = {
                    //An update with the same updateid replaces the previous one
                    updateId: messageId + "_" + timeStampFirstOnscreen,
                    messageId,
                    updateType,
                    timeStampFirstOnscreen,
                    _internal: {
                        messageTopWhenFirstOnscreen,
                    },
                };
                const vectorsInfo = that.processScrollVectors(
                    that.loggedMessages[messageId],
                    vectors,
                    messageSelector,
                    viewportGeometry
                );

                let retVal = {
                    _internal: _,
                    ...that.loggedMessages[messageId],
                    ...vectorsInfo.metrics,
                };

                if (that.debugScrollLogging) {
                    console.log(
                        "Mock-wrote new log for message",
                        messageId,
                        ": ",
                        retVal
                    );
                }
            }

            /*if (that.debugScrollLogging && msgFractionInsideViewPort > 0) {
              console.log("message", messageId, " % on screen: ", msgFractionInsideViewPort * 100, "messageWhiteSpaceRatio", messageWhiteSpaceRatio);
            }*/
        });
        let oldestMessageInLogTimeStamp;
        _.each(that.loggedMessages, function (log, id) {
            if (log.updateType === ATTENTION_UPDATE_FINAL) {
                if (that.debugScrollLogging) {
                    console.log(
                        "message",
                        id,
                        " processed FINAL update, deleting from log..."
                    );
                }
                delete that.loggedMessages[id];
            } else {
                if (!log.timeStampFirstOnscreen) {
                    throw new Error("timeStampFirstOnscreen is invalid");
                }
                if (
                    !oldestMessageInLogTimeStamp ||
                    log.timeStampFirstOnscreen < oldestMessageInLogTimeStamp
                ) {
                    oldestMessageInLogTimeStamp = log.timeStampFirstOnscreen;
                }
            }
        });
        that.pruneOldScrollVectors(oldestMessageInLogTimeStamp);
    }

    /**
     * Prune all scroll event older than the last one PRIOR to the
     * timestamp provided
     * @param {*} timeStamp
     */
    pruneOldScrollVectors(timeStamp) {
        let that = this;

        if (!timeStamp) {
            throw new Error(
                "pruneOldScrollVectors: missing of invalid timestamp"
            );
        }
        let firstNewerVectorIndex = that.vectorStack.findIndex((vector) => {
            if (vector.timeStamp === undefined) {
                throw new Error(
                    "pruneOldScrollVectors: Unable to process vector"
                );
            }
            return vector.timeStamp >= timeStamp;
        });

        //console.log("firstNewerVectorIndex ", firstNewerVectorIndex, "newer than", timeStamp);
        let lastIndexToKeep = firstNewerVectorIndex - 1; //We also need the vector that brought the message onscreen, which is just before the one when the message was detected onscreen.
        if (lastIndexToKeep >= 0) {
            //console.log("pruning vectors indexes  0 to ", lastIndexToKeep);
            that.vectorStack.splice(0, lastIndexToKeep + 1);
        }
    }
    /**
     * @param {*} scrollLoggerMessageInfo The attention information last logged about the message
     * @param {*} vectors
     * @param {*} messageSelector
     */
    processScrollVectors(
        scrollLoggerMessageInfo,
        vectors,
        messageSelector,
        viewportGeometry
    ) {
        let that = this;
        //TODO: While unlikely the height has changed spotaneously during scroll, it is very possible that a message has been expanded from preview, or that the thread branch has been collapsed.  The scroll vectors do not log this.  To fix  "properly", we would need to timestamp individual message size change.  A quick and more realistic improvement would be to immediately force a final update when the message changed geometry, and prune it's history.  It could be done during checkMessagesOnscreen.

        let CURRENT_FONT_SIZE_PX = parseFloat(
            messageSelector.find(".message-body").first().css("font-size")
        );
        if (!CURRENT_FONT_SIZE_PX) {
            throw new Error("Unable to detemine current font size");
        }
        const { viewportHeight } = viewportGeometry;
        const { messageTopWhenFirstOnscreen } = scrollLoggerMessageInfo;
        //Estimate from scrool net distance.
        const fractionViewportCoveredByMessage = "TODO";
        //Note:  After testing, the width() (a jquery function) is the proper
        // content width, as a float, excluding padding and margins.
        let messageTextWidth = messageSelector.width();

        let //Character per line:  normally between 45 to 75, 66 is considered ideal.
            //Average character per line = div width / font size in px*0.4
            CURRENT_CHARACTERS_PER_LINE =
                messageTextWidth / (CURRENT_FONT_SIZE_PX * 0.4);

        let //(gotcha:  ideally substract non-character size of message, but still count header)
            ESTIMATED_LINE_HEIGHT = 1.5 * CURRENT_FONT_SIZE_PX;

        let //Character per word: 5.1 average for english language + 1 space => multipy WPM*5 to get CPM
            CARACTERS_PER_WORD = 5.1 + 1;

        let WORDS_PER_LINE = CURRENT_CHARACTERS_PER_LINE / CARACTERS_PER_WORD;

        let messageSizeViewportRatio;
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

        let initialAccumulator = {
            _internal: {
                lastValidDirection: undefined,
                cumulativeDownDistancePx: 0,
                cumulativeUpDistancePx: 0,
            },
            metrics: {
                totalDurationMs: 0,
                numDirectionChanges: 0,
                numDirectionChangesWhileMessageCoversViewport: 0,
                numEstimatedInternalDirectionChanges: 0,
                scrollUpAvgWPM: undefined,
                numSlowScrolls: "TODO",
                fractionInSlowScrolls: "TODO",
                totalEffectiveFractionOfMessageScrolled: 0,
                effectiveWpmIfUserReadWholeMessage: undefined,
                /*
                Other TODO:
                fractionOfMessageThatReachedViewport?
                estimatedFractionOfMessageRead?
                */
            },
        };
        /** Compute the direction of the scroll
                Reminder:  scrollTop is the position of the scrollBar, so always positive
                top() of an element is the distance from top of the container, also always positive
                So, scrolling UP (content moves up), scrollTop increases
                When reading, we expect direction to be UP
                
         * @param {number} distance - px
         */
        function getDirection(distance) {
            switch (distance / Math.abs(distance)) {
                case -1:
                    return DIRECTION_DOWN;
                case 1:
                    return DIRECTION_UP;
                case 0:
                    return DIRECTION_NONE;
                default:
                    throw new Error("Unable to compute scroll direction");
            }
        }

        const reducer = (acc, vector, idx, vectors) => {
            if (idx !== 0) {
                //Skip the first vector, as it's the one BEFORE the message was onscreen

                let previousVector = vectors[idx - 1];
                //console.log("reducer()", idx, vector, previousVector);

                let distancePx = vector.scrollTop - previousVector.scrollTop;

                /* START Recompose message geometry at prior to vector 
                We only consider the geometry at the start of the scroll, 
                not the average of the start and end.  Saves CPU, and error should average out while the message is onscreen
                */
                const netDistanceScrolledSoFar =
                    acc.metrics.cumulativeUpDistancePx -
                    acc._internal.cumulativeDownDistancePx;
                const messageTopAtStartOfVector =
                    messageTopWhenFirstOnscreen - netDistanceScrolledSoFar;
                const messageGeometry = that.getMessageGeometry(
                    messageSelector,
                    messageTopAtStartOfVector
                );

                const messageVsViewportGeometry = that.getMessageVsViewportGeometry(
                    messageGeometry,
                    viewportGeometry
                );
                const {
                    msgFractionInsideViewPort: msgFractionInsideViewPortAtStartOfVector,
                    viewportFractionCoveredByMsg,
                    msgScrollableDistance,
                } = messageVsViewportGeometry;
                /*console.log("netMove: ", netDistanceScrolledSoFar, 
                  "messageTopWhenFirstOnscreen", messageTopWhenFirstOnscreen, "messageTopAtStartOfVector", messageTopAtStartOfVector, "msgFractionInsideViewPortAtStartOfVector:", msgFractionInsideViewPortAtStartOfVector);*/
                /* END Recompose message geometry at prior to vector */

                let previousDirection = acc._internal.lastValidDirection;
                let direction = getDirection(distancePx);

                if (direction !== DIRECTION_NONE) {
                    //We actually moved
                    acc._internal.lastValidDirection = direction;
                }
                if (
                    direction !== DIRECTION_NONE && //We actually moved
                    previousDirection && //Not the first movement
                    previousDirection !== direction
                ) {
                    //We changed direction
                    acc.metrics.numDirectionChanges += 1;
                    if (viewportFractionCoveredByMsg >= 1) {
                        //An internal message scroll to re-read something, very strong
                        //attention signal
                        acc.metrics.numDirectionChangesWhileMessageCoversViewport += 1;
                    }
                    acc.metrics.numEstimatedInternalDirectionChanges +=
                        1 * viewportFractionCoveredByMsg;
                }

                let duration = vector.timeStamp - previousVector.timeStamp;
                acc.metrics.totalDurationMs += duration;
                if (direction === DIRECTION_DOWN) {
                    acc._internal.cumulativeDownDistancePx += Math.abs(
                        distancePx
                    );
                }
                if (direction === DIRECTION_UP) {
                    acc._internal.cumulativeUpDistancePx += Math.abs(
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
                    acc.metrics.totalEffectiveFractionOfMessageScrolled += currEffectiveFractionOfMessageScrolled;
                    const fractionOfTotalUpScroll =
                        distancePx / acc._internal.cumulativeUpDistancePx;
                    let scrollLines = distancePx / ESTIMATED_LINE_HEIGHT;
                    let elapsedMilliseconds =
                        vector.timeStamp - previousVector.timeStamp;
                    let scrollLinesPerMinute =
                        (scrollLines / elapsedMilliseconds) * 1000 * 60;
                    let scrollWordsPerMinute =
                        scrollLinesPerMinute * WORDS_PER_LINE;
                    if (acc.metrics.scrollUpAvgWPM) {
                        acc.metrics.scrollUpAvgWPM =
                            fractionOfTotalUpScroll * scrollWordsPerMinute +
                            (1 - fractionOfTotalUpScroll) *
                                acc.metrics.scrollUpAvgWPM;
                    } else {
                        acc.metrics.scrollUpAvgWPM = scrollWordsPerMinute;
                    }
                    //Règle de 3...
                    acc.metrics.effectiveWpmIfUserReadWholeMessage =
                        acc.metrics.scrollUpAvgWPM /
                        acc.metrics.totalEffectiveFractionOfMessageScrolled;
                }

                if (false && that.debugScrollLogging) {
                    console.log("reducer(): DEBUG for idx", idx, ":", {
                        ...acc.metrics,
                    });
                }
            }
            return acc;
        };
        return vectors.reduce(reducer, initialAccumulator);
    }
}

export default ScrollLogger;
