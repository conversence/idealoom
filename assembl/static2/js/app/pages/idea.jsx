import { List, Map } from 'immutable';
import React from 'react';
import { connect } from 'react-redux';
import { Translate } from 'react-redux-i18n';
import { compose, graphql } from 'react-apollo';
import { Grid } from 'react-bootstrap';
import { createSelector } from 'reselect';

import { postsByIdSelector, localeSelector } from '../selectors';
import { togglePostResponses } from '../actions/postsActions';
import Header from '../components/debate/common/header';
import IdeaWithPosts from '../graphql/IdeaWithPosts.graphql';
import InfiniteSeparator from '../components/common/infiniteSeparator';
import Post, { connectPostToState, PostFolded } from '../components/debate/thread/post';
import Tree from '../components/common/tree';
import withLoadingIndicator from '../components/common/withLoadingIndicator';

import { MainDiscussion } from './../components/debate/thread/mainDiscussion';

export const transformPosts = (posts) => {
  let postsByParent = Map();
  posts.forEach((p) => {
    const items = postsByParent.get(p.parentId, List());
    postsByParent = postsByParent.set(p.parentId, items.push(p));
  });

  const getChildren = (id) => {
    return postsByParent.get(id, List()).toJS().map((post) => {
      return { ...post, children: getChildren(post.id) };
    });
  };

  return postsByParent
    .get(null, List())
    .map((p) => {
      return { ...p, children: getChildren(p.id) };
    })
    .toJS();
};

class Idea extends React.Component {
  render() {
    const { toggleItem } = this.props;
    const { idea } = this.props.data;
    const rawPosts = idea.posts.edges.map((e) => {
      return e.node;
    });
    const posts = transformPosts(rawPosts);

    return (
      <div className="idea">
        <Header title={idea.title} imgUrl={idea.imgUrl} identifier="thread" />

        <section className="post-section">
          <Grid fluid className="background-light">
            <div className="max-container">
              <MainDiscussion
                ideaId={idea.id}
                disccussionSubject={this.disccussionSubject} // TODO: use state values when using redux state
                disccussionBody={this.disccussionBody} // TODO: use state values when using redux state
              />
              <div className="content-section">
                <Tree
                  connectChildFunction={connectPostToState}
                  data={posts}
                  InnerComponent={Post}
                  InnerComponentFolded={PostFolded}
                  noRowsRenderer={() => {
                    return <div className="center"><Translate value="debate.thread.noPostsInThread" /></div>;
                  }}
                  SeparatorComponent={InfiniteSeparator}
                  toggleItem={toggleItem}
                />
              </div>
            </div>
          </Grid>
        </section>
      </div>
    );
  }
}

const mapStateToProps = createSelector(postsByIdSelector, localeSelector, (postsById, locale) => {
  const expandedItems = postsById
    .filter((item) => {
      return item.get('showResponses', false);
    })
    .keySeq()
    .toArray();
  return {
    expandedItems: expandedItems,
    lang: locale
  };
});

const mapDispatchToProps = (dispatch) => {
  return {
    toggleItem: (id) => {
      return dispatch(togglePostResponses(id));
    }
  };
};

export default compose(connect(mapStateToProps, mapDispatchToProps), graphql(IdeaWithPosts), withLoadingIndicator())(Idea);