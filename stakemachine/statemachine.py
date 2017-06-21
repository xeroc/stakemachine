class StateMachine():
    def __init__(self, *args, **kwargs):
        self.states = set()
        self.state = None

    def add_state(self, state):
        self.states.add(state)

    def set_state(self, state):
        assert state in self.states, "Unknown State"
        self.state = state

    def get_state(self):
        return self.state
