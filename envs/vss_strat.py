import math
import random
from typing import Dict

import gym
import numpy as np
from rsoccer_gym.Entities import Ball, Frame, Robot
from rsoccer_gym.Utils import KDTree
from rsoccer_gym.Utils.Utils import OrnsteinUhlenbeckAction
from rsoccer_gym.vss.vss_gym_base import VSSBaseEnv


class VSSStratEnv(VSSBaseEnv):
    """This environment controls a single robot in a VSS soccer League 3v3 match 


        Description:
        Observation:
            Type: Box(40)
            Normalized Bounds to [-1.25, 1.25]
            Num             Observation normalized  
            0               Ball X
            1               Ball Y
            2               Ball Vx
            3               Ball Vy
            4 + (7 * i)     id i Blue Robot X
            5 + (7 * i)     id i Blue Robot Y
            6 + (7 * i)     id i Blue Robot sin(theta)
            7 + (7 * i)     id i Blue Robot cos(theta)
            8 + (7 * i)     id i Blue Robot Vx
            9  + (7 * i)    id i Blue Robot Vy
            10 + (7 * i)    id i Blue Robot v_theta
            25 + (5 * i)    id i Yellow Robot X
            26 + (5 * i)    id i Yellow Robot Y
            27 + (5 * i)    id i Yellow Robot Vx
            28 + (5 * i)    id i Yellow Robot Vy
            29 + (5 * i)    id i Yellow Robot v_theta
        Actions:
            Type: Box(2, )
            Num     Action
            0       id 0 Blue Left Wheel Speed  (%)
            1       id 0 Blue Right Wheel Speed (%)
        Reward:
            Sum of Rewards:
                Goal
                Ball Potential Gradient
                Move to Ball
                Energy Penalty
        Starting State:
            Randomized Robots and Ball initial Position
        Episode Termination:
            30 seconds match time
    """

    def __init__(self, stratified=True, n_robots_blue=3, n_robots_yellow=3):
        super().__init__(
            field_type=0, n_robots_blue=n_robots_blue, n_robots_yellow=n_robots_yellow, time_step=0.025
        )

        self.action_space = gym.spaces.Box(low=-1, high=1, shape=(2,), dtype=np.float32)
        self.observation_space = gym.spaces.Box(
            low=-self.NORM_BOUNDS, high=self.NORM_BOUNDS, shape=(40,), dtype=np.float32
        )

        # Initialize Class Atributes
        self.previous_ball_potential = None
        self.actions: Dict = None
        self.cumulative_reward_info = None
        self.v_wheel_deadzone = 0.05
        self.energy_scale = 40000
        self.grad_scale = 0.75
        self.move_scale = 120

        self.ou_actions = []
        for i in range(self.n_robots_blue + self.n_robots_yellow):
            self.ou_actions.append(
                OrnsteinUhlenbeckAction(self.action_space, dt=self.time_step)
            )
        
        self.ori_weights = np.array([0.6600, 0.3200, 0.0053, 0.0080])
        self.stratified = stratified

        self.r_min = np.array([0.0, 0.0, -2.0, 0.0])
        self.r_max = np.array([0.5, 1.0, -1.0, 1.0])

        if stratified:
            self.num_rewards = 4

        print("agents/envs/vss_strat Environment initialized")

    def reset(self):
        self.actions = None
        self.cumulative_reward_info = None
        self.previous_ball_potential = None
        for ou in self.ou_actions:
            ou.reset()

        return super().reset()

    def step(self, action):
        observation, strat_reward, done, _ = super().step(action)

        original_reward = (strat_reward * self.ori_weights).sum()


        if not self.stratified:
            reward = original_reward
        else:
            reward = strat_reward

        self.cumulative_reward_info['Original_reward'] += original_reward
        
        info = self.cumulative_reward_info
        info['goal_blue'] = 1 if strat_reward[3] == 1 else 0
        info['goal_yellow'] = 1 if strat_reward[3] == -1 else 0
        
        return observation, reward, done, info

    def _frame_to_observations(self):

        observation = []

        observation.append(self.norm_pos(self.frame.ball.x))
        observation.append(self.norm_pos(self.frame.ball.y))
        observation.append(self.norm_v(self.frame.ball.v_x))
        observation.append(self.norm_v(self.frame.ball.v_y))

        for i in range(self.n_robots_blue):
            observation.append(self.norm_pos(self.frame.robots_blue[i].x))
            observation.append(self.norm_pos(self.frame.robots_blue[i].y))
            observation.append(np.sin(np.deg2rad(self.frame.robots_blue[i].theta)))
            observation.append(np.cos(np.deg2rad(self.frame.robots_blue[i].theta)))
            observation.append(self.norm_v(self.frame.robots_blue[i].v_x))
            observation.append(self.norm_v(self.frame.robots_blue[i].v_y))
            observation.append(self.norm_w(self.frame.robots_blue[i].v_theta))

        for i in range(self.n_robots_yellow):
            observation.append(self.norm_pos(self.frame.robots_yellow[i].x))
            observation.append(self.norm_pos(self.frame.robots_yellow[i].y))
            observation.append(self.norm_v(self.frame.robots_yellow[i].v_x))
            observation.append(self.norm_v(self.frame.robots_yellow[i].v_y))
            observation.append(self.norm_w(self.frame.robots_yellow[i].v_theta))

        return np.array(observation, dtype=np.float32)

    def _get_commands(self, actions):
        commands = []
        self.actions = {}

        self.actions[0] = actions
        v_wheel0, v_wheel1 = self._actions_to_v_wheels(actions)
        commands.append(Robot(yellow=False, id=0, v_wheel0=v_wheel0, v_wheel1=v_wheel1))

        # Send random commands to the other robots
        for i in range(1, self.n_robots_blue):
            actions = self.ou_actions[i].sample()
            self.actions[i] = actions
            v_wheel0, v_wheel1 = self._actions_to_v_wheels(actions)
            commands.append(
                Robot(yellow=False, id=i, v_wheel0=v_wheel0, v_wheel1=v_wheel1)
            )
        for i in range(self.n_robots_yellow):
            actions = self.ou_actions[self.n_robots_blue + i].sample()
            v_wheel0, v_wheel1 = self._actions_to_v_wheels(actions)
            commands.append(
                Robot(yellow=True, id=i, v_wheel0=v_wheel0, v_wheel1=v_wheel1)
            )

        return commands

    def _calculate_reward_and_done(self):
        rewards = np.zeros(4)
        goal_reward = 0
        move_reward = 0
        grad_ball_potential = 0
        energy_penalty = 0

        if self.cumulative_reward_info is None:
            self.cumulative_reward_info = {
                "reward_move": 0,
                "reward_ball_grad": 0,
                "reward_energy": 0,
                "reward_goal": 0,
                "Original_reward": 0,
            }

        # Check if goal ocurred
        if self.frame.ball.x > (self.field.length / 2):
            goal_reward = 1
        elif self.frame.ball.x < -(self.field.length / 2):
            goal_reward = -1
        else:
            if self.last_frame is not None:
                # Calculate Move ball
                move_reward = self.__move_reward()
                # Calculate ball potential
                grad_ball_potential = self.__ball_grad()
                # Calculate Energy penalty
                energy_penalty = self.__energy_penalty()

        rewards[0] += move_reward
        rewards[1] += grad_ball_potential
        rewards[2] += energy_penalty
        rewards[3] += goal_reward

        self.cumulative_reward_info["reward_move"] += rewards[0]
        self.cumulative_reward_info["reward_ball_grad"] += rewards[1]
        self.cumulative_reward_info["reward_energy"] += rewards[2]
        self.cumulative_reward_info["reward_goal"] += rewards[3]
        
        return rewards, (goal_reward != 0)

    def _get_initial_positions_frame(self):
        """Returns the position of each robot and ball for the initial frame"""
        field_half_length = self.field.length / 2
        field_half_width = self.field.width / 2

        def x():
            return random.uniform(-field_half_length + 0.1, field_half_length - 0.1)

        def y():
            return random.uniform(-field_half_width + 0.1, field_half_width - 0.1)

        def theta():
            return random.uniform(0, 360)

        pos_frame: Frame = Frame()

        pos_frame.ball = Ball(x=x(), y=y())

        min_dist = 0.1

        places = KDTree()
        places.insert((pos_frame.ball.x, pos_frame.ball.y))

        for i in range(self.n_robots_blue):
            pos = (x(), y())
            while places.get_nearest(pos)[1] < min_dist:
                pos = (x(), y())

            places.insert(pos)
            pos_frame.robots_blue[i] = Robot(x=pos[0], y=pos[1], theta=theta())

        for i in range(self.n_robots_yellow):
            pos = (x(), y())
            while places.get_nearest(pos)[1] < min_dist:
                pos = (x(), y())

            places.insert(pos)
            pos_frame.robots_yellow[i] = Robot(x=pos[0], y=pos[1], theta=theta())

        return pos_frame

    def _actions_to_v_wheels(self, actions):
        left_wheel_speed = actions[0] * self.max_v
        right_wheel_speed = actions[1] * self.max_v

        left_wheel_speed, right_wheel_speed = np.clip(
            (left_wheel_speed, right_wheel_speed), -self.max_v, self.max_v
        )

        # Deadzone
        if -self.v_wheel_deadzone < left_wheel_speed < self.v_wheel_deadzone:
            left_wheel_speed = 0

        if -self.v_wheel_deadzone < right_wheel_speed < self.v_wheel_deadzone:
            right_wheel_speed = 0

        # Convert to rad/s
        left_wheel_speed /= self.field.rbt_wheel_radius
        right_wheel_speed /= self.field.rbt_wheel_radius

        return left_wheel_speed, right_wheel_speed

    def __ball_grad(self):
        assert self.last_frame is not None

        # Calculate previous ball dist
        last_ball = self.last_frame.ball
        last_ball_pos = np.array([last_ball.x, last_ball.y])
        goal_pos = np.array([self.field.length / 2, 0])
        last_ball_dist = np.linalg.norm(goal_pos - last_ball_pos)

        # Calculate new ball dist
        ball = self.frame.ball
        ball_pos = np.array([ball.x, ball.y])
        ball_dist = np.linalg.norm(goal_pos - ball_pos)

        ball_dist_rw = last_ball_dist - ball_dist
        ball_dist_rw = ball_dist_rw / self.grad_scale

        return ball_dist_rw

    def __move_reward(self):
        """Calculate Move to ball reward

        Cosine between the robot vel vector and the vector robot -> ball.
        This indicates rather the robot is moving towards the ball or not.
        """

        ball = np.array([self.frame.ball.x, self.frame.ball.y])
        robot = np.array([self.frame.robots_blue[0].x, self.frame.robots_blue[0].y])
        robot_vel = np.array(
            [self.frame.robots_blue[0].v_x, self.frame.robots_blue[0].v_y]
        )
        robot_ball = ball - robot
        robot_ball = robot_ball / np.linalg.norm(robot_ball)

        move_reward = np.dot(robot_ball, robot_vel)
        return move_reward / self.move_scale

    def __energy_penalty(self):
        """Calculates the energy penalty"""

        en_penalty_1 = abs(self.sent_commands[0].v_wheel0)
        en_penalty_2 = abs(self.sent_commands[0].v_wheel1)
        energy_penalty = -(en_penalty_1 + en_penalty_2)

        return energy_penalty / self.energy_scale
