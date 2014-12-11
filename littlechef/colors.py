from fabric import env, colors


def _colorize(color, msg):
    if env.no_color:
        return msg
    return colors.getattr(color)(msg)

red = lambda msg: _colorize('red', msg)
green = lambda msg: _colorize('green', msg)
yellow = lambda msg: _colorize('yellow', msg)
