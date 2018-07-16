
class BaseAlgorithm:
    """ This is a base-class meant to be inherited from to implement new algorithms.
        Each new algorithm should override the schedule method.
    """
    def __init__(self, interface):
        pass

    def schedule(self, active_EVs):
        """ Creates a schedule of charging rates for each EV in the active_EV list.
            NOT IMPLEMENTED IN BaseAlgorithm!!!

        :param active_EVs: List of EVs who should be scheduled
        :return: A dictionary with key: EV id and value: schedule of charging rates as a list.
        """

        schedules = {}
        return schedules
    
    def run(self):
        """ Runs one instance of the scheduling algorithm and submits the resulting schedule.

        :return: None
        """
        active_EVs = self.interface.get_active_EVs()
        schedules = self.schedule(active_EVs)
        self.interface.submit_schedules(schedules)

    def interface_setup(self, interface):
        self.interface = interface
        self.max_charging_rate = interface.get_max_charging_rate()

    def get_increased_charging_rate(self, current_rate, allowable_rates):
        new_index = allowable_rates.index(current_rate) + 1
        if new_index >= len(allowable_rates):
            new_index = len(allowable_rates) - 1
        return allowable_rates[new_index]

    def get_decreased_charging_rate(self, current_rate, allowable_rates):
        new_index = allowable_rates.index(current_rate) - 1
        if new_index < 0:
            new_index = 0
        return allowable_rates[new_index]

    def get_decreased_charging_rate_nz(self, current_rate, allowable_rates):
        new_index = allowable_rates.index(current_rate) - 1
        if new_index < 1:
            new_index = 1
        return allowable_rates[new_index]

class EarliestDeadlineFirstAlgorithm(BaseAlgorithm):

    def __init__(self):
        pass

    def schedule(self, active_EVs):
        schedule = {}
        earliest_EV = self.get_earliest_EV(active_EVs)
        last_applied_pilot_signals = self.interface.get_last_applied_pilot_signals()
        for ev in active_EVs:
            charge_rates = []
            last_pilot_signal = 0
            allowable_pilot_signals = self.interface.get_allowable_pilot_signals(ev.station_id)
            if ev.session_id in last_applied_pilot_signals:
                last_pilot_signal = last_applied_pilot_signals[ev.session_id]
            if ev.session_id == earliest_EV.session_id:
                new_rate = self.get_increased_charging_rate(last_pilot_signal, allowable_pilot_signals)
                charge_rates.append(new_rate)
            else:
                new_rate = self.get_decreased_charging_rate_nz(last_pilot_signal, allowable_pilot_signals)
                charge_rates.append(new_rate)
            schedule[ev.session_id] = charge_rates
        return schedule

    def get_earliest_EV(self, EVs):
        earliest_EV = None
        for ev in EVs:
            if earliest_EV == None or earliest_EV.departure > ev.departure:
                earliest_EV = ev
        return earliest_EV

class LeastLaxityFirstAlgorithm(BaseAlgorithm):

    def __init__(self):
        pass

    def schedule(self, active_EVs):
        schedule = {}
        least_slack_EV = self.get_least_slack_EV(active_EVs)
        last_applied_pilot_signals = self.interface.get_last_applied_pilot_signals()
        for ev in active_EVs:
            charge_rates = []
            last_pilot_signal = 0
            allowable_pilot_signals = self.interface.get_allowable_pilot_signals(ev.station_id)
            if ev.session_id in last_applied_pilot_signals:
                last_pilot_signal = last_applied_pilot_signals[ev.session_id]
            if ev.session_id == least_slack_EV.session_id:
                new_rate = self.get_increased_charging_rate(last_pilot_signal, allowable_pilot_signals)
                charge_rates.append(new_rate)
            else:
                new_rate = self.get_decreased_charging_rate_nz(last_pilot_signal, allowable_pilot_signals)
                charge_rates.append(new_rate)
            schedule[ev.session_id] = charge_rates
        return schedule

        return schedule

    def get_least_slack_EV(self, EVs):
        least_slack_EV = None
        least_slack = 0
        for ev in EVs:
            current_slack = self.get_slack_time(ev)
            if least_slack_EV == None or least_slack > current_slack:
                least_slack = current_slack
                least_slack_EV = ev
        return least_slack_EV

    def get_slack_time(self, EV):
        slack = (EV.requested_energy - EV.energy_delivered) / self.max_charging_rate
        return slack

class MLLF(BaseAlgorithm):
    '''
    Multicore Least Laxity First

    This algorithm builds upon the Least Laxity scheduling algorithm but also includes
    the possiblity to have many processes (sessions) running at the same time.
    The algorithm calculates a laxity value of every session and then rank them according
    to this value. The sessions with least laxity get moved to a queue which will get prioritized in
    the charging schedule. A session in this queue will receive the maximum pilot signal. The other
    sessions will get the minumum pilot signal

    There is an option to select if the charging schedule will allow preemtion of the active queue.
    If there is no preemtion allowed a session once entered the active queue will not leave until it
    has finished charging. If preemtion is allowed the ready queue will get recalculated every iteration
    to allow new sessions with smaller laxity to interrupt the current sessions in the queue.
    '''

    def __init__(self, preemption=False, queue_length=4):
        self.queue = []
        self.preemption = preemption
        self.queue_length = queue_length

    def schedule(self, active_EVs):
        schedule = {}
        current_time = self.interface.get_current_time()
        last_applied_pilot_signals = self.interface.get_last_applied_pilot_signals()

        # No preemtion: check queue and remove non-active EVs
        # Preemtion: Always empty the queue
        for session_id in self.queue:
            if self.preemption:
                self.queue = []
            else:
                found = False
                for ev in active_EVs:
                    if ev.session_id == session_id:
                        found = True
                        break
                if found == False:
                    self.queue.remove(session_id)

        # choose the EVs that should be evaluated for laxity and then sort them
        # If no preemtion the EVs already in the queue should be omitted.
        ev_laxity = []
        for ev in active_EVs:
            if self.preemption or (not self.preemption and ev.session_id not in self.queue):
                ev_info = {'session_id': ev.session_id, 'laxity': self.get_laxity(ev, current_time)}
                ev_laxity.append(ev_info)

        sorted_ev_laxity = self.sort_by_laxity(ev_laxity)

        # add the EVs to the queue
        ql = len(self.queue)
        for i in range(min(self.queue_length - ql, len(sorted_ev_laxity))):
            ev = sorted_ev_laxity[i]
            self.queue.append(ev['session_id'])

        # calculate the new pilot signals
        for ev in active_EVs:
            charge_rates = []
            last_pilot_signal = 0
            allowable_pilot_signals = self.interface.get_allowable_pilot_signals(ev.station_id)
            if ev.session_id in last_applied_pilot_signals:
                last_pilot_signal = last_applied_pilot_signals[ev.session_id]
            # determine pilot signal
            if ev.session_id in self.queue:
                new_rate = self.get_increased_charging_rate(last_pilot_signal, allowable_pilot_signals)
                charge_rates.append(new_rate)
            else:
                new_rate = self.get_decreased_charging_rate_nz(last_pilot_signal, allowable_pilot_signals)
                charge_rates.append(new_rate)
            schedule[ev.session_id] = charge_rates
        return schedule


    def get_laxity(self, EV, current_time):
        laxity = (EV.departure - current_time) - (EV.requested_energy - EV.energy_delivered) / self.max_charging_rate
        return laxity

    def sort_by_laxity(self, list):
        return sorted(list, key=lambda ev: ev['laxity'])
