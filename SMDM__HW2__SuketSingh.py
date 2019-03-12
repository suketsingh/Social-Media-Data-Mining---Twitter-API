import twitter
import sys
import time
from urllib.error import URLError
from http.client import BadStatusLine
import json
import twitter
from sys import maxsize as maxint
from functools import partial
import networkx as nx
import matplotlib.pyplot as plt


def oauth_login():
    CONSUMER_KEY = '5TyUXR9iR2SP82wlBNEz6arXJ'
    CONSUMER_SECRET = 'ZBwc5G9eznld6CSy7fWuIEJ33cvsM1WkulgJIFmSGQCqYhJdVm'
    OAUTH_TOKEN = '1101003429240020992-TsfhFZ7crsz1INY7W1GefQjasTYWIc'
    OAUTH_TOKEN_SECRET = 'fsc9iE6XJbiT506Lqb6ufUptS4MKcYONPXfoK9SGVqovN'
    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET,
                               CONSUMER_KEY, CONSUMER_SECRET)
    twitter_api = twitter.Twitter(auth=auth)
    return twitter_api


def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600:  # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e

        # See https://developer.twitter.com/en/docs/basics/response-codes
        # for common codes

        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429:
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60 * 15 + 5)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e  # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'.format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise


def get_friends_ids(twitter_api, screen_name=None, user_id=None,
                    friends_limit=5000):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), "Must have screen_name or user_id, but not both"

    # get 5000 friends
    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)

    friends_ids = []

    # api call to get friends using partial
    for twitter_api_func, limit, ids, label in [
        [get_friends_ids, friends_limit, friends_ids, "friends"]
    ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else:  # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            print('{0} has total {1} friends'.format((user_id or screen_name), len(ids)), file
            =sys.stderr)

            if len(ids) >= limit or response is None:
                break

    # return no of friends upto the limit asked
    return friends_ids[:friends_limit]


def get_followers_ids(twitter_api, screen_name=None, user_id=None,
                      followers_limit=5000):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), "Must have screen_name or user_id, but not both"

    # get 5000 followers
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)

    followers_ids = []

    # api call to get followerss using partial
    for twitter_api_func, limit, ids, label in [
        [get_followers_ids, followers_limit, followers_ids, "followers"]
    ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else:  # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            print('{0} has total {1} followers'.format((user_id or screen_name), len(ids)), file
            =sys.stderr)

            if len(ids) >= limit or response is None:
                break

    # return no of followers upto the limit asked
    return followers_ids[:followers_limit]


def get_top_five_user_profile(twitter_api, screen_names=None, user_ids=None):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None), "Must have screen_names or user_ids, but not both"

    items_to_info = {}

    items = screen_names or user_ids

    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See http://bit.ly/2Gcjfzr for details.

        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
                                            screen_name=items_str)
        else:  # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
                                            user_id=items_str)

        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else:  # user_ids
                items_to_info[user_info['id']] = user_info

    top_five_sorted_keys = sorted(items_to_info, key=lambda x: (items_to_info[x]['followers_count']), reverse=True)[0:5]
    return top_five_sorted_keys


def crawl(twitter_api, screen_name, limit=5000, network_population=100):
    seed_id = str(twitter_api.users.show(screen_name=screen_name)['id'])
    seed_as_int = int(seed_id)

    # start creating the graph
    Graph = nx.Graph()
    # add the first node
    Graph.add_node(seed_as_int)

    # find seed's friend and followers
    next_queue_friends_ids = get_friends_ids(twitter_api, user_id=seed_id, friends_limit=limit)
    next_queue_follower_ids = get_followers_ids(twitter_api, user_id=seed_id, followers_limit=limit)

    # find the common ones between them by taking an intersection of both the sets
    reciprocal_friends = list(set(next_queue_friends_ids).intersection(set(next_queue_follower_ids)))

    # this is the final network nodes as a list
    final_network = []

    # get the top 5 profiles from the list of reciprocal friends
    top_next_profiles = get_top_five_user_profile(twitter_api, user_ids=reciprocal_friends)

    # add them to the graph and link them
    for ids in top_next_profiles:
        Graph.add_node(ids)
        Graph.add_edge(seed_as_int, ids)
    final_network.extend(top_next_profiles)

    # run outer looop until the final network has sufficient no of nodes
    while len(final_network) <= network_population:
        (temp_queue_to_crawl, top_next_profiles) = (top_next_profiles, [])

        for fid in temp_queue_to_crawl:
            # first get his friends and followers
            friend_ids = get_friends_ids(twitter_api, user_id=fid, friends_limit=limit)
            follower_ids = get_followers_ids(twitter_api, user_id=fid, followers_limit=limit)
            # find their intersection
            reciprocal_friends_for_current_id = list(set(friend_ids).intersection(set(follower_ids)))
            print(f"{fid} has {len(reciprocal_friends_for_current_id)} reciprocal friends")

            # find the top 5 reciprocal friends and add them to the queue
            current_top_profiles = get_top_five_user_profile(twitter_api, user_ids=reciprocal_friends_for_current_id)

            # add them to the graph and link them to their common reciprocal friend
            for ids in current_top_profiles:
                Graph.add_node(ids)
                Graph.add_edge(fid, ids)

            final_network.extend(current_top_profiles)
            print(f"We now have a network of {len(final_network)} friends")

            # condition to end early
            if len(final_network) >= 100:
                break

            top_next_profiles += current_top_profiles

    print(f"No of nodes : {nx.number_of_nodes(Graph)}")
    print(f"No of edges : {nx.number_of_edges(Graph)}")
    print(f"Diameter of network : {nx.diameter(Graph)}")
    print(f"Average distance of network: {nx.average_shortest_path_length(Graph, weight=None, method='dijkstra')}")

    # drawing the graph as a kamada kawai layout
    nx.draw_kamada_kawai(Graph)
    nx.draw_networkx_labels(Graph, pos=nx.nx.kamada_kawai_layout(Graph), font_size=10, alpha=0.5)
    plt.draw()
    plt.show()

    return final_network


twitter_api = oauth_login()

screen_name = 'ben'

hundred_users = crawl(twitter_api, screen_name)

print(hundred_users)
