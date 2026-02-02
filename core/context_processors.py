def is_engineer(request):
    if request.user.is_authenticated:
        return {'is_engineer': request.user.groups.filter(name='Engineer').exists()}
    return {'is_engineer': False}
