import docker
import docker.errors
import errno
import json
from jupyter_kernel_mgmt.managerabc import KernelManager2ABC
from jupyter_core.paths import jupyter_runtime_dir
from jupyter_core.utils import ensure_dir_exists
import os
from pathlib import Path
from requests import Timeout
import signal
import stat
from tempfile import TemporaryDirectory
import uuid
import warnings

PORTS = {
    'shell_port': 9001,
    'iopub_port': 9002,
    'stdin_port': 9003,
    'control_port': 9004,
    'hb_port': 9005,
}

def set_sticky_bit(fname):
    """Set the sticky bit on the file and its parent directory.

    This stops it being deleted by periodic cleanup of XDG_RUNTIME_DIR.
    """
    if not hasattr(stat, 'S_ISVTX'):
        return

    paths = [fname]
    runtime_dir = os.path.dirname(fname)
    if runtime_dir:
        paths.append(runtime_dir)
    for path in paths:
        permissions = os.stat(path).st_mode
        new_permissions = permissions | stat.S_ISVTX
        if new_permissions != permissions:
            try:
                os.chmod(path, new_permissions)
            except OSError as e:
                if e.errno == errno.EPERM and path == runtime_dir:
                    # suppress permission errors setting sticky bit on runtime_dir,
                    # which we may not own.
                    pass
                else:
                    # failed to set sticky bit, probably not a big deal
                    warnings.warn(
                        "Failed to set sticky bit on %r: %s"
                        "\nProbably not a big deal, but runtime files may be cleaned up periodically." % (path, e),
                        RuntimeWarning,
                    )

def make_connection_file(in_dir):
    """Generates a JSON config file to start the kernel inside the docker file
    """
    cfg = {
        'transport': 'tcp',
        'ip': '0.0.0.0',
        'key': str(uuid.uuid4()),
        'signature_scheme': 'hmac-sha256',
    }
    cfg.update(PORTS)

    fname = Path(in_dir, 'kernel.json')
    with fname.open('w') as f:
        f.write(json.dumps(cfg, indent=2))

    set_sticky_bit(str(fname))

    return cfg


def launch(image, cwd):
    d = os.path.join(jupyter_runtime_dir(), 'docker_kernels')
    ensure_dir_exists(d)
    set_sticky_bit(d)
    conn_file_tmpdir = TemporaryDirectory(dir=d)
    conn_info = make_connection_file(conn_file_tmpdir.name)

    container = docker.from_env().containers.run(image, detach=True,
        volumes = {
            conn_file_tmpdir.name: {'bind': '/connect', 'mode': 'rw'},
            cwd: {'bind': '/working', 'mode': 'rw'},
        }
    )

    container.reload()  # Need this to get the IP address
    ip = container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
    if not ip:
        raise RuntimeError("No IP address for docker container")
    print(container.attrs['NetworkSettings']['Networks'])
    conn_info['ip'] = ip

    return conn_info, DockerKernelManager(container, conn_file_tmpdir)

class DockerKernelManager(KernelManager2ABC):
    def __init__(self, container, conn_file_tmpdir):
        self.container = container
        self.conn_file_tmpdir = conn_file_tmpdir

    def is_alive(self):
        try:
            self.container.reload()
        except docker.errors.NotFound:
            return False
        return self.container.status == 'running'

    def wait(self, timeout):
        try:
            self.container.wait(timeout=timeout)
        except Timeout:
            pass
        return self.is_alive()
    
    def interrupt(self):
        self.signal(signal.SIGINT)
    
    def kill(self):
        print("Status in kill", self.container.status)
        self.signal(signal.SIGKILL)
    
    def signal(self, signum):
        self.container.kill(signum)
    
    def cleanup(self):
        self.container.stop()
        self.container.remove()
        self.conn_file_tmpdir.cleanup()
