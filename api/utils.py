import os
import tempfile
import errno

def decode_values(redis_values):
    return {k.decode('utf-8'): v.decode('utf-8') for k, v in redis_values.items()}

def makedirs_ignore(path, mode):
    """
    Creates the given directory (and any parents), but succeeds if it already
    exists.
    """
    try:
        os.makedirs(path, mode)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

# Would be nice if Python did this for us: http://bugs.python.org/issue8604
class AtomicFileReplacement(object):
    """
    Replace a file atomically

    Easiest usage is as a context manager, but create_temp, destroy_temp
    and replace_dest can also be called directly if needed
    """

    def __init__(self, dest_path, mode=0o644):
        self.dest_path = dest_path
        self.mode = mode
        self._temp_info = None

    @property
    def temp_file(self):
        if not self._temp_info:
            msg = "Replacement for %r not yet created" % self.dest_path
            raise RuntimeError(msg)
        return self._temp_info[0]

    def create_temp(self):
        """Create the temporary file that may later be renamed"""
        dirname, basename = os.path.split(self.dest_path)
        fd, temp_path = tempfile.mkstemp(prefix='.' + basename, dir=dirname)
        try:
            f = os.fdopen(fd, 'w')
        except:
            os.unlink(temp_path)
            raise
        self._temp_info = f, fd, temp_path
        return f

    def destroy_temp(self):
        """Ensure the temporary file (if any) is destroyed"""
        temp_info = self._temp_info
        if temp_info is None:
            return
        f, fd, temp_path = temp_info
        try:
            os.unlink(temp_path)
        except:
            pass
        self._temp_info = None

    def replace_dest(self):
        """Move the temporary file to its final destination"""
        temp_info = self._temp_info
        if temp_info is None:
            msg = "Replacement for %r not yet created" % self.dest_path
            raise RuntimeError(msg)
        f, fd, temp_path = temp_info
        f.flush()
        os.fchmod(fd, self.mode)
        os.rename(temp_path, self.dest_path)
        self._temp_info = None

    def __enter__(self):
        return self.create_temp()

    def __exit__(self, exc_type, exc, exc_tb):
        if exc_type is None:
            self.replace_dest()
        else:
            self.destroy_temp()

# Backwards compatibility alias
atomically_replaced_file = AtomicFileReplacement
