# Morfologia: OPEN e CLOSE — pixel a pixel

> Kernel: **3×3**.

> Cada célula = 1 pixel. 

`W` = 255 (branco). 

`.` = 0 (preto).

```
Erosão:   C sobrevive como W  somente se TODOS os vizinhos forem W.
Dilatação: C vira W           se QUALQUER vizinho for W.
```

---

## Imagem de entrada — `mascara_binaria`

```
      0  1  2  3  4  5  6  7  8  9 10 11 12
  0:  .  .  .  .  .  .  .  .  .  .  .  .  .
  1:  .  .  .  .  .  .  .  .  .  .  .  .  .
  2:  .  .  W  W  W  W  W  W  W  W  W  .  .
  3:  .  .  W  W  W  W  W  W  W  W  W  .  .
  4:  .  .  W  W  W  W  W  W  W  W  W  .  .
  5:  .  .  W  W  W  .  .  W  W  W  W  .  .   ← buraco (cols 5–6)
  6:  .  .  W  W  W  .  .  W  W  W  W  .  .   ← buraco (cols 5–6)
  7:  .  .  W  W  W  W  W  W  W  W  W  .  .
  8:  .  .  W  W  W  W  W  W  W  W  W  .  .
  9:  .  .  W  W  W  W  W  W  W  W  W  .  .
 10:  .  .  .  .  .  .  W  .  .  .  .  .  .   ← ruído isolado (col 6)
 11:  .  .  .  .  .  .  .  .  .  .  .  .  .
```

---

# OPEN — Erosão → Dilatação

## Após Erosão

Borda exterior eliminada. Pixels adjacentes ao buraco eliminados. Buraco cresce. Ruído apagado.

```
      0  1  2  3  4  5  6  7  8  9 10 11 12
  0:  .  .  .  .  .  .  .  .  .  .  .  .  .
  1:  .  .  .  .  .  .  .  .  .  .  .  .  .
  2:  .  .  .  .  .  .  .  .  .  .  .  .  .   ← borda sumiu
  3:  .  .  .  W  W  W  W  W  W  W  .  .  .   ← cols 3–9 sobrevivem
  4:  .  .  .  W  .  .  .  .  W  W  .  .  .   ← cols 4–7 eliminados (vizinhos do buraco)
  5:  .  .  .  W  .  .  .  .  W  W  .  .  .
  6:  .  .  .  W  .  .  .  .  W  W  .  .  .
  7:  .  .  .  W  .  .  .  .  W  W  .  .  .
  8:  .  .  .  W  W  W  W  W  W  W  .  .  .   ← cols 3–9 sobrevivem
  9:  .  .  .  .  .  .  .  .  .  .  .  .  .   ← borda sumiu
 10:  .  .  .  .  .  .  .  .  .  .  .  .  .   ← ruído morto ✓
 11:  .  .  .  .  .  .  .  .  .  .  .  .  .
```

## Após Dilatação — resultado do OPEN

Borda exterior restaurada. Regiões adjacentes ao buraco restauradas pelas linhas 3 e 8.
Centro do buraco (linhas 5–6, cols 5–6) **não restaurado** — estava longe demais de qualquer W na erosão.

```
      0  1  2  3  4  5  6  7  8  9 10 11 12
  0:  .  .  .  .  .  .  .  .  .  .  .  .  .
  1:  .  .  .  .  .  .  .  .  .  .  .  .  .
  2:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← borda restaurada
  3:  .  .  W  W  W  W  W  W  W  W  W  .  .
  4:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← restaurado pela linha 3
  5:  .  .  W  W  W  .  .  W  W  W  W  .  .   ← buraco ainda existe
  6:  .  .  W  W  W  .  .  W  W  W  W  .  .   ← buraco ainda existe
  7:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← restaurado pela linha 8
  8:  .  .  W  W  W  W  W  W  W  W  W  .  .
  9:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← borda restaurada
 10:  .  .  .  .  .  .  .  .  .  .  .  .  .   ← ruído NÃO voltou ✓
 11:  .  .  .  .  .  .  .  .  .  .  .  .  .
```

---

# CLOSE — Dilatação → Erosão

## Após Dilatação

Borda exterior infla 1 pixel para fora. Os W das bordas do buraco se encontram no meio e o fecham.

```
      0  1  2  3  4  5  6  7  8  9 10 11 12
  0:  .  .  .  .  .  .  .  .  .  .  .  .  .
  1:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← inflou para fora
  2:  .  W  W  W  W  W  W  W  W  W  W  W  .   ← inflou para fora
  3:  .  W  W  W  W  W  W  W  W  W  W  W  .
  4:  .  W  W  W  W  W  W  W  W  W  W  W  .
  5:  .  W  W  W  W  W  W  W  W  W  W  W  .   ← BURACO FECHADO ✓
  6:  .  W  W  W  W  W  W  W  W  W  W  W  .   ← BURACO FECHADO ✓
  7:  .  W  W  W  W  W  W  W  W  W  W  W  .
  8:  .  W  W  W  W  W  W  W  W  W  W  W  .
  9:  .  W  W  W  W  W  W  W  W  W  W  W  .
 10:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← inflou para fora
 11:  .  .  .  .  .  .  .  .  .  .  .  .  .
```

## Após Erosão — `mascara_limpa`

Borda inflada removida. Ex-buraco sobrevive: estava completamente cercado de W → passa no teste.

```
      0  1  2  3  4  5  6  7  8  9 10 11 12
  0:  .  .  .  .  .  .  .  .  .  .  .  .  .
  1:  .  .  .  .  .  .  .  .  .  .  .  .  .
  2:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← borda inflada removida
  3:  .  .  W  W  W  W  W  W  W  W  W  .  .
  4:  .  .  W  W  W  W  W  W  W  W  W  .  .
  5:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← BURACO FECHADO ✓
  6:  .  .  W  W  W  W  W  W  W  W  W  .  .   ← BURACO FECHADO ✓
  7:  .  .  W  W  W  W  W  W  W  W  W  .  .
  8:  .  .  W  W  W  W  W  W  W  W  W  .  .
  9:  .  .  W  W  W  W  W  W  W  W  W  .  .
 10:  .  .  .  .  .  .  .  .  .  .  .  .  .   ← ruído permanece morto ✓
 11:  .  .  .  .  .  .  .  .  .  .  .  .  .
```

Idêntico ao blob original — sem buraco, sem ruído.

---

## Referência no código

```python
# core/detector_classico.py — linhas 72–77

mascara_limpa = cv2.morphologyEx(
    mascara_binaria, cv2.MORPH_OPEN, self.kernel        # erosão → dilatação
)
mascara_limpa = cv2.morphologyEx(
    mascara_limpa, cv2.MORPH_CLOSE, self.kernel, iterations=2  # dilatação → erosão (×2)
)
```
