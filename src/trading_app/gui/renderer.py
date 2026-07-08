def handle_batch(batch):
    # called at controlled 20ms cadence
    app.renderer.render(batch)
