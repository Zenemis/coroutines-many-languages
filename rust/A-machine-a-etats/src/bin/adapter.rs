//! Adaptateur de conformité de la variante A.
//!
//! Lit les commandes sur stdin et écrit un événement par ligne sur stdout.
//! Protocole : conformance/PROTOCOLE.md. Corps à implémenter : conformance/CATALOGUE.md.

use coroutines_a::{Coroutine, cr_return, cr_yield};

fn main() {
    let _feu = Coroutine::new(vec![
        cr_yield(|| {
            println!("print allumage");
            "vert"
        }),
        cr_yield(|| "orange"),
        cr_yield(|| "rouge"),
        cr_return(|| "eteint"),
    ]);

    let _cuisinier = Coroutine::new(vec![
        cr_yield(|| println!("je coupe les légumes")),
        cr_yield(|| println!("je fais cuire")),
        cr_return(|| println!("le plat est prêt")),
    ]);
}
