import numpy as np

"""
Drawing labels of geometrical objects (with indices)
"""
class LabelVisualiser:
    def __init__(self, std_size = 48, sub_size = 30, sub_lower = 10):
        self.lookup_table = dict()
        self.std_size = std_size
        self.sub_size = sub_size
        self.sub_lower = sub_lower

    """
    parse(cr, s) converts the string into instructions for drawing
    the parsing rules are approximatelly:
     * if there is an underscore in the string,
       it swaps the index mode and normal mode
     * otherwise, there are three basic character types:
       uppercase letters, lowercase letters, numbers
       * change between these types causes mode swap
       * other characters, such as comma, does not cause mode swap
       * prime is never put into index
    The output is of the form
    (texts, subscripts, extents).
    extents are analogous of the standard cairo.text_extents
    texts and subscripts are lists of instructions of the form
    (x, y, text) for
      cr.move_to(x,y)
      cr.show_text(text)
    Note that the parsing results are cached, so the parse function should
    be always called with the same font set in the cairo context.
    """
    def parse(self, cr, s):
        if s in self.lookup_table:
            return self.lookup_table[s]

        self.cr = cr
        self.texts = []
        self.subscripts = []
        self.cur_x = 0
        self.min_coor = None
        self.max_coor = None

        self.std_chars = []
        self.sub_chars = []

        has_underscore = '_' in s

        last_sub = None
        last_ctype = None
        for c in s:
            if c == '_':
                last_sub = not last_sub
                continue

            cur_ctype = self._char_type(c)
            if has_underscore:
                cur_sub = last_sub
            else:
                if cur_ctype is None or last_ctype is None:
                    cur_sub = last_sub
                elif cur_ctype == last_ctype: cur_sub = last_sub
                elif c == "'": cur_sub = False
                else: cur_sub = not last_sub
            
            if cur_sub: self._add_sub_char(c)
            else: self._add_std_char(c)
            if c != "'":
                last_sub = cur_sub
                last_ctype = cur_ctype

        self._finish_block()

        if self.min_coor is None:
            self.min_coor = np.zeros(2)
            self.max_coor = np.zeros(2)
        min_x, min_y = self.min_coor
        width, height = self.max_coor - self.min_coor
        extents = min_x, min_y, width, height, self.cur_x, 0

        self.cr = None

        result = self.texts, self.subscripts, extents
        self.lookup_table[s] = result
        return result

    # draw the text in the format given by self.parse
    def show(self, cr, texts, subscripts):
        cr.set_font_size(self.std_size)
        for x,y,text in texts:
            cr.move_to(x,y)
            cr.show_text(text)
        cr.set_font_size(self.sub_size)
        for x,y,text in subscripts:
            cr.move_to(x,y)
            cr.show_text(text)
        cr.new_path()

    # draw so that the center of the text is at (0,0)
    def show_center(self, cr, texts, subscripts, extents):
        x, y, width, height, dx, dy = extents
        cr.save()
        cr.translate(*self.get_center_start(extents))
        self.show(cr, texts, subscripts)
        cr.restore()
    def get_center_start(self, extents):
        x, y, width, height, dx, dy = extents
        return np.array([-(x+width/2), -(y+height/2)])

    # draw text in "edit mode", as is, without smart parsing, with a cursor
    def show_edit(self, cr, text, curs_index, position = (0,0),
                  curs_color = (0,0,1), curs_by = 'I', curs_w = 2):

        cr.save()
        cr.translate(*position)
        cr.set_font_size(self.std_size)
        _, curs_y, _, curs_h, _, _ = cr.text_extents(curs_by)
        curs_pos = cr.text_extents(text[:curs_index])[4]

        cr.move_to(0, 0)
        cr.show_text(text)

        cr.rectangle(curs_pos, curs_y, curs_w, curs_h)
        cr.set_source_rgb(*curs_color)
        cr.fill()

        cr.restore()

    ### Helper functions for parsing

    def _char_type(self, c):
        if c.islower(): return 0
        elif c.isupper(): return 1
        elif c.isnumeric(): return 2
        elif c == "'": return 3
        else: return None

    def _add_text(self, text, cur_y, size, l):
        if text == "": return self.cur_x
        l.append((self.cur_x, cur_y, text))
        self.cr.set_font_size(size)
        x, y, width, height, dx, dy = self.cr.text_extents(text)
        min_coor = np.array([self.cur_x+x, cur_y+y])
        max_coor = min_coor + (width, height)
        if self.min_coor is None:
            self.min_coor = min_coor
            self.max_coor = max_coor
        else:
            self.min_coor = np.minimum(self.min_coor, min_coor)
            self.max_coor = np.maximum(self.max_coor, max_coor)

        return self.cur_x + dx

    def _finish_block(self):
        text = ''.join(self.std_chars)
        self.std_chars = []
        subscript = ''.join(self.sub_chars)
        self.sub_chars = []

        next_x1 = self._add_text(text, 0, self.std_size, self.texts)
        self.cur_x += self.cr.text_extents(text.rstrip("'"))[4]
        next_x2 = self._add_text(subscript, self.sub_lower, self.sub_size, self.subscripts)
        self.cur_x = max(next_x1, next_x2)

    def _add_std_char(self, c):
        if self.sub_chars and c != "'":
            self._finish_block()
        self.std_chars.append(c)
    def _add_sub_char(self, c):
        self.sub_chars.append(c)
