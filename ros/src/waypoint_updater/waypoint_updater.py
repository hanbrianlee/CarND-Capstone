#!/usr/bin/env python

import rospy
from geometry_msgs.msg import PoseStamped
from styx_msgs.msg import Lane, Waypoint
from scipy.spatial import KDTree
from std_msgs.msg import Int32

import numpy as np

import math

'''
This node will publish waypoints from the car's current position to some `x` distance ahead.

As mentioned in the doc, you should ideally first implement a version which does not care
about traffic lights or obstacles.

Once you have created dbw_node, you will update this node to use the status of traffic lights too.

Please note that our simulator also provides the exact location of traffic lights and their
current status in `/vehicle/traffic_lights` message. You can use this message to build this node
as well as to verify your TL classifier.

TODO (for Yousuf and Aaron): Stopline location for each traffic light.
'''


class WaypointUpdater(object):

    def __init__(self):
        rospy.init_node('waypoint_updater')

        # Add member variables that we need in this class
        self.waypoints_base = None
        self.waypoints_2d = None
        self.waypoints_tree = None
        self.pose = None
        self.stopline_wp_idx = -1

        # Get parameters
        self.lookahead_waypoints = rospy.get_param('~lookahead_waypoints', 30)
        self.max_deceleration = rospy.get_param('~max_deceleration', 0.75)


        # Register message listeners
        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)

        # TODO: Add a subscriber for /traffic_waypoint
        rospy.Subscriber('/traffic_waypoint', Int32, self.traffic_cb)

        # Register message publishers
        self.final_waypoints_pub = rospy.Publisher('final_waypoints', Lane, queue_size=1)

    def run(self):
        """
        Runs the operations of this waypoint updater
        """
        rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            if self.pose and self.waypoints_base and self.waypoints_tree:
                # get closest waypoint
                closest_waypoint_idx = self.get_closest_waypoint_idx()
                self.publish_waypoints(closest_waypoint_idx)
            rate.sleep()

    def get_closest_waypoint_idx(self):
        # extract the x,y position of the pose
        x = self.pose.pose.position.x
        y = self.pose.pose.position.y

        # query the closest waypoint from our index
        closest_idx = self.waypoints_tree.query([x, y], 1)[1]

        # check if the closest waypoint is in front or back of our vehicle
        closest_coord = self.waypoints_2d[closest_idx]
        prev_coord = self.waypoints_2d[closest_idx-1]

        # Equation for hyperplan through closest_coords
        cl_vect = np.array(closest_coord)
        prev_vect = np.array(prev_coord)
        pos_vect = np.array([x, y])

        val = np.dot(cl_vect - prev_vect, pos_vect - cl_vect)
        if val > 0:
            closest_idx = (closest_idx + 1) % len(self.waypoints_2d)
        return closest_idx

    #def publish_waypoints(self, closest_idx):
    #    lane = Lane()
    #    lane.header = self.waypoints_base.header
    #    lane.waypoints = self.waypoints_base.waypoints[closest_idx:closest_idx + self.lookahead_waypoints]
    #    self.final_waypoints_pub.publish(lane)


    def publish_waypoints(self, closest_idx):
        final_lane = self.generate_lane()
        self.final_waypoints_pub.publish(final_lane)

    def generate_lane(self):
        lane = Lane()

        # start and end of lane
        closest_idx = self.get_closest_waypoint_idx()
        farthest_idx = closest_idx + self.lookahead_waypoints
        base_waypoints = self.waypoints_base.waypoints[closest_idx:farthest_idx]

        # check if there is a traffic light in range of Lane
        if self.stopline_wp_idx == -1 or (self.stopline_wp_idx >= farthest_idx):
            lane.waypoints = base_waypoints
        else:
            lane.waypoints = self.decelerate_waypoints(base_waypoints, closest_idx)

        return lane

    def decelerate_waypoints(self, waypoints, closest_idx):
        temp = []
        for i, wp in enumerate(waypoints):
            p = Waypoint()
            p.pose = wp.pose # do we need this?!

            # to stop the vehicle behind the stopline, reduce by 3 (distance from vehicles center to nose)
            stop_idx = max(self.stopline_wp_idx - closest_idx - 3, 0)

            dist = self.distance(waypoints, i, stop_idx)
            vel = (self.max_deceleration * dist)
            if vel < 1:
                vel = 0

            # only consider velocity values smaller than target speed
            p.twist.twist.linear.x = min(vel, wp.twist.twist.linear.x)
            temp.append(p)

        return temp

    def pose_cb(self, msg):
        """
        Callback of the pose message
        :param msg: the updated pose message
        """
        self.pose = msg

    def waypoints_cb(self, waypoints):
        """
        Callback of the base waypoints message.
        :param waypoints: the received base waypoints
        """
        self.waypoints_base = waypoints
        self.waypoints_2d = [[waypoint.pose.pose.position.x, waypoint.pose.pose.position.y]
                             for waypoint in waypoints.waypoints]
        self.waypoints_tree = KDTree(self.waypoints_2d)

    def traffic_cb(self, msg):
        # TODO: Callback for /traffic_waypoint message. Implement
        self.stopline_wp_idx = msg.data


    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        pass

    @staticmethod
    def get_waypoint_velocity(waypoint):
        return waypoint.twist.twist.linear.x

    @staticmethod
    def set_waypoint_velocity(waypoints, waypoint, velocity):
        waypoints[waypoint].twist.twist.linear.x = velocity

    @staticmethod
    def distance(waypoints, wp1, wp2):
        dist = 0
        dl = lambda a, b: math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
        for i in range(wp1, wp2 + 1):
            dist += dl(waypoints[wp1].pose.pose.position, waypoints[i].pose.pose.position)
            wp1 = i
        return dist


if __name__ == '__main__':
    try:
        WaypointUpdater().run()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')
