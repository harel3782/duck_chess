#include <pybind11/pybind11.h>
#include <cstdint>

namespace py = pybind11;

typedef uint64_t Bitboard;

// Bit manipulation macros
#define set_bit(bb, sq) ((bb) |= (1ULL << (sq)))
#define get_bit(bb, sq) ((bb) & (1ULL << (sq)))
#define pop_bit(bb, sq) ((bb) &= ~(1ULL << (sq)))

class GameState {
public:
    Bitboard w_rooks;
    Bitboard w_king;
    Bitboard b_king;
    Bitboard duck;

    GameState() {
        w_rooks = 0;
        w_king = 0;
        b_king = 0;
        duck = 0;
    }

    // Set up a test board (White Rook A1, King E1, Black King E8, Duck D4)
    void init_test_board() {
        set_bit(w_rooks, 0);  // A1
        set_bit(w_king, 4);   // E1
        set_bit(b_king, 60);  // E8
        set_bit(duck, 27);    // D4
    }

    // Teleport the duck
    void move_duck(int square) {
        duck = 0;
        set_bit(duck, square);
    }
};

// Python Bindings
PYBIND11_MODULE(duck_engine, m) {
    py::class_<GameState>(m, "GameState")
        .def(py::init<>())
        .def("init_test_board", &GameState::init_test_board)
        .def("move_duck", &GameState::move_duck)
        .def_readwrite("w_rooks", &GameState::w_rooks)
        .def_readwrite("w_king", &GameState::w_king)
        .def_readwrite("b_king", &GameState::b_king)
        .def_readwrite("duck", &GameState::duck);
}