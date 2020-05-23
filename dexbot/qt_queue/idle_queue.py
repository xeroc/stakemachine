import queue

idle_loop = queue.Queue()


def idle_add(func, *args, **kwargs):
    def idle():
        func(*args, **kwargs)

    idle_loop.put(idle)
